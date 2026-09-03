`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// admm_top -- scaled-form ADMM, one iteration per FSM pass.
//
//   minimise  (1/2)||H x - y||^2 + g(z)   s.t.  x = z
//
//   x^{k+1} = M ( q + rho (z^k - u^k) ),   M = (H'H + rho I)^-1,  q = H'y
//   z^{k+1} = prox_{g/rho}( x^{k+1} + u^k )
//   u^{k+1} = u^k + x^{k+1} - z^{k+1}
//
// M and q are formed once per channel coherence interval by a preprocessing
// unit outside this IP (standard practice for MIMO detector accelerators) and
// presented on weight_bus / q_bus. The accelerator owns the iterative core.
// M is the stationary weight -> maps exactly onto the weight-stationary array.
//
// Convergence test uses the L-infinity norm, which is a SUFFICIENT condition
// for the L2 criterion in the theory: ||r||_2 <= sqrt(N) ||r||_inf, so testing
// ||r||_inf <= eps/sqrt(N) implies ||r||_2 <= eps. Costs N abs + a compare
// tree instead of N multipliers and a square root.
// ============================================================================
module admm_top #(
    parameter integer N          = 8,
    parameter integer ASYMMETRIC = 1,
    parameter integer F_L1_P  = -1,
    parameter integer F_BOX_P = -1,
    parameter integer F_L2_P  = -1,
    parameter integer USE_DSP_L2 = 1,
    parameter integer RHO_SHIFT  = 0,      // rho = 2^RHO_SHIFT
    parameter integer KAPPA_Q16  = 32'sd6554,
    parameter integer BOX_HI_Q16 = 32'sd65536,
    parameter integer BOX_LO_Q16 = -32'sd65536,
    parameter integer GAMMA_Q16  = 32'sd43691
)(
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          start,
    input  wire [1:0]                    prox_mode,
    input  wire [7:0]                    max_iter,
    input  wire signed [`W_MAIN-1:0]     eps_pri,     // ||r||_inf threshold
    input  wire signed [`W_MAIN-1:0]     eps_dual,    // ||s||_inf threshold
    input  wire [(N*N*`W_MAIN)-1:0]      weight_bus,  // M
    input  wire [(N*`W_MAIN)-1:0]        q_bus,       // q = H'y
    output reg                           done,
    output reg  [7:0]                    iter_count,
    output wire [(N*`W_MAIN)-1:0]        z_out
);
    localparam integer W       = `W_MAIN;
    localparam integer LATENCY = 2*N + 2;

    // S_VCOMB and S_RED are pipeline stages added purely for timing:
    //   x_reg -> sat_add(v=x+u) -> prox lane -> z_out    was -11.6 ns
    //   x_reg -> sat_add(r)     -> abs -> maxtree -> cmp was -18.9 ns
    // Registering v and the residual magnitudes splits both paths.
    localparam [3:0] S_IDLE = 4'd0, S_LOADW = 4'd1, S_PRECOMB = 4'd2,
                     S_FLUSH= 4'd3, S_CAPX  = 4'd4, S_VCOMB   = 4'd5,
                     S_PROX = 4'd6, S_DUAL  = 4'd7, S_RED     = 4'd8,
                     S_CHECK= 4'd9, S_DONE  = 4'd10;

    reg [3:0]  state;
    reg [15:0] flush_cnt;
    reg        load_w_ctrl;

    reg  [(N*W)-1:0] z_reg, z_prev, u_reg, x_reg, w_reg, v_reg;
    reg  [(N*W)-1:0] r_abs_reg, s_abs_reg;
    wire [(N*W)-1:0] y_arr, z_new;

    // -------------------------------------------------------------------
    // x-update: w = q + rho*(z - u)   ->   systolic array
    // -------------------------------------------------------------------
    wire [(N*W)-1:0] w_comb;
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : G_PRECOMB
            wire signed [W-1:0] zi = z_reg[(i*W) +: W];
            wire signed [W-1:0] ui = u_reg[(i*W) +: W];
            wire signed [W-1:0] qi = q_bus[(i*W) +: W];
            wire signed [W-1:0] d, ds;
            sat_add  #(.W(W))              u_sub (.a(zi), .b(ui), .sub(1'b1), .y(d));
            sat_shift#(.W(W), .SH(RHO_SHIFT)) u_rho (.din(d), .dout(ds));
            sat_add  #(.W(W))              u_add (.a(qi), .b(ds), .sub(1'b0),
                                                  .y(w_comb[(i*W) +: W]));
        end
    endgenerate

    wire [(N*W)-1:0] v_comb;
    generate
        for (i = 0; i < N; i = i + 1) begin : G_VCOMB
            sat_add #(.W(W)) u_v (.a(x_reg[(i*W) +: W]), .b(u_reg[(i*W) +: W]),
                                  .sub(1'b0), .y(v_comb[(i*W) +: W]));
        end
    endgenerate

    systolic_array #(.N(N)) u_array (
        .clk(clk), .rst_n(rst_n), .load_w(load_w_ctrl),
        .weight_bus(weight_bus), .w_in(w_reg), .y_out(y_arr)
    );

    // -------------------------------------------------------------------
    // z-update: v = x + u  ->  prox lanes
    // -------------------------------------------------------------------
    reg prox_en;
    generate
        for (i = 0; i < N; i = i + 1) begin : G_PROX
            reconfigurable_prox #(
                .ASYMMETRIC(ASYMMETRIC), .USE_DSP_L2(USE_DSP_L2),
                .F_L1_P(F_L1_P), .F_BOX_P(F_BOX_P), .F_L2_P(F_L2_P),
                .KAPPA_Q16(KAPPA_Q16),
                .BOX_HI_Q16(BOX_HI_Q16), .BOX_LO_Q16(BOX_LO_Q16),
                .GAMMA_Q16(GAMMA_Q16)
            ) u_prox (
                .clk(clk), .rst_n(rst_n), .en(prox_en),
                .prox_mode(prox_mode), .v_in(v_reg[(i*W) +: W]),
                .z_out(z_new[(i*W) +: W])
            );
        end
    endgenerate

    // -------------------------------------------------------------------
    // u-update and residuals
    //   r = x^{k+1} - z^{k+1}      s = rho ( z^{k+1} - z^k )
    // -------------------------------------------------------------------
    wire [(N*W)-1:0] u_next;
    wire [(N*W)-1:0] r_abs, s_abs;
    generate
        for (i = 0; i < N; i = i + 1) begin : G_DUAL
            wire signed [W-1:0] xi = x_reg[(i*W) +: W];
            wire signed [W-1:0] ui = u_reg[(i*W) +: W];
            wire signed [W-1:0] zn = z_new[(i*W) +: W];
            wire signed [W-1:0] zo = z_reg[(i*W) +: W];
            wire signed [W-1:0] ri, un, dz, si;

            sat_add #(.W(W)) u_r  (.a(xi), .b(zn), .sub(1'b1), .y(ri));
            sat_add #(.W(W)) u_un (.a(ui), .b(ri), .sub(1'b0),
                                   .y(u_next[(i*W) +: W]));
            sat_add #(.W(W)) u_dz (.a(zn), .b(zo), .sub(1'b1), .y(dz));
            sat_shift #(.W(W), .SH(RHO_SHIFT)) u_s (.din(dz), .dout(si));

            assign r_abs[(i*W) +: W] = ri[W-1] ? -ri : ri;
            assign s_abs[(i*W) +: W] = si[W-1] ? -si : si;
        end
    endgenerate

    // L-infinity reduction: balanced tree over REGISTERED magnitudes.
    wire [W-1:0] r_max, s_max;
    max_tree #(.W(W), .N(N)) u_rmax (.din(r_abs_reg), .dout(r_max));
    max_tree #(.W(W), .N(N)) u_smax (.din(s_abs_reg), .dout(s_max));

    reg converged;

    // -------------------------------------------------------------------
    // FSM
    // -------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE; done <= 1'b0; load_w_ctrl <= 1'b0;
            prox_en <= 1'b0; flush_cnt <= 16'd0; iter_count <= 8'd0;
            z_reg <= {(N*W){1'b0}}; z_prev <= {(N*W){1'b0}};
            u_reg <= {(N*W){1'b0}}; x_reg <= {(N*W){1'b0}};
            w_reg <= {(N*W){1'b0}}; v_reg  <= {(N*W){1'b0}};
            r_abs_reg <= {(N*W){1'b0}}; s_abs_reg <= {(N*W){1'b0}};
            converged <= 1'b0;
        end else begin
            prox_en <= 1'b0;
            case (state)
                S_IDLE: begin
                    done <= 1'b0; converged <= 1'b0;
                    if (start) begin
                        iter_count  <= 8'd0;
                        z_reg <= {(N*W){1'b0}};
                        z_prev<= {(N*W){1'b0}};
                        u_reg <= {(N*W){1'b0}};
                        load_w_ctrl <= 1'b1;
                        state <= S_LOADW;
                    end
                end

                S_LOADW: begin
                    load_w_ctrl <= 1'b0;   // weights trapped; bus may go quiet
                    state <= S_PRECOMB;
                end

                S_PRECOMB: begin
                    w_reg     <= w_comb;
                    flush_cnt <= 16'd0;
                    state     <= S_FLUSH;
                end

                S_FLUSH: begin
                    if (flush_cnt == LATENCY[15:0]) state <= S_CAPX;
                    else flush_cnt <= flush_cnt + 16'd1;
                end

                S_CAPX: begin
                    x_reg <= y_arr;
                    state <= S_VCOMB;
                end

                S_VCOMB: begin
                    v_reg   <= v_comb;     // break x_reg -> prox path
                    prox_en <= 1'b1;
                    state   <= S_PROX;
                end

                S_PROX: begin
                    prox_en <= 1'b1;       // z_new registers this cycle
                    state   <= S_DUAL;
                end

                S_DUAL: begin
                    u_reg     <= u_next;
                    z_prev    <= z_reg;
                    z_reg     <= z_new;
                    r_abs_reg <= r_abs;    // break x_reg -> converged path
                    s_abs_reg <= s_abs;
                    state     <= S_RED;
                end

                S_RED: begin
                    converged <= (r_max <= eps_pri[W-1:0]) &&
                                 (s_max <= eps_dual[W-1:0]);
                    state     <= S_CHECK;
                end

                S_CHECK: begin
                    iter_count <= iter_count + 8'd1;
                    if (converged || (iter_count + 8'd1 >= max_iter)) state <= S_DONE;
                    else                                              state <= S_PRECOMB;
                end

                S_DONE: begin
                    done  <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    assign z_out = z_reg;
endmodule
