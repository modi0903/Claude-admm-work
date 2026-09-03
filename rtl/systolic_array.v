`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// systolic_array -- N x N weight-stationary array computing y = M * w.
//
// M[i][j] is trapped in PE(i,j). w[j] enters column j and is pipelined
// DOWNWARD one register per row; psum for output row i accumulates LEFT to
// RIGHT. The vertical x pipeline is kept (rather than broadcasting w) purely
// to break the fanout -- with N=32 a broadcast net is the critical path.
//
// NO INPUT PRE-SKEW. ADMM is sequentially dependent: iteration k+1 needs
// x^{k+1}, so there is never more than one vector in flight. w is held stable
// for the whole pass and every psum settles to the correct value
// simultaneously after LATENCY cycles. The 8x8 triangular skew register file
// in the previous revision was N*N = 64 registers of dead area feeding a
// steady-state computation, and it was reported as part of the accelerator's
// LUT/FF footprint.
//
// Throughput is therefore 1 mat-vec per LATENCY cycles, not 1/cycle. State
// that in the paper -- it is what determines Mb/s.
// ============================================================================
module systolic_array #(
    parameter integer N = 8
)(
    input  wire                                 clk,
    input  wire                                 rst_n,
    input  wire                                 load_w,
    input  wire [(N*N*`W_MAIN)-1:0]             weight_bus,   // M, row-major
    input  wire [(N*`W_MAIN)-1:0]               w_in,         // input vector
    output wire [(N*`W_MAIN)-1:0]               y_out         // saturated Q2.16
);
    // x propagation (N rows) + psum traversal (N cols) + 2 slack
    localparam integer LATENCY = 2*N + 2;

    wire signed [`W_MAIN-1:0] x_wire    [0:N][0:N-1];
    wire signed [`W_ACC-1:0]  psum_wire [0:N-1][0:N];

    genvar i, j;
    generate
        for (j = 0; j < N; j = j + 1) begin : G_XIN
            assign x_wire[0][j] = w_in[(j*`W_MAIN) +: `W_MAIN];
        end
        for (i = 0; i < N; i = i + 1) begin : G_PSUM0
            assign psum_wire[i][0] = {`W_ACC{1'b0}};
        end

        for (i = 0; i < N; i = i + 1) begin : ROW
            for (j = 0; j < N; j = j + 1) begin : COL
                wire signed [`W_MAIN-1:0] wgt =
                    weight_bus[(((i*N)+j)*`W_MAIN) +: `W_MAIN];
                pe_mac u_pe (
                    .clk       (clk),
                    .rst_n     (rst_n),
                    .load_w    (load_w),
                    .weight_in (wgt),
                    .x_in      (x_wire[i][j]),
                    .psum_in   (psum_wire[i][j]),
                    .x_out     (x_wire[i+1][j]),
                    .psum_out  (psum_wire[i][j+1])
                );
            end
        end

        // Q8.32 accumulator -> Q2.16 with round + saturate.
        for (i = 0; i < N; i = i + 1) begin : G_YOUT
            q_narrow #(.W_IN(`W_ACC), .F_IN(`F_ACC),
                       .W_OUT(`W_MAIN), .F_OUT(`F_MAIN))
                u_cast (.din(psum_wire[i][N]),
                        .dout(y_out[(i*`W_MAIN) +: `W_MAIN]));
        end
    endgenerate
endmodule
