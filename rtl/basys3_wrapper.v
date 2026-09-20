`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// basys3_wrapper -- board bring-up and wall-power harness for admm_top.
//
// WHY THIS SHAPE. The board has 16 switches; one solve needs an 8x8 matrix
// plus an 8-vector at W_MAIN bits, far more than the switches carry. So the
// problem comes from ROM (initialised from the same golden .mem files the
// gate-level regression uses) and the answer leaves over UART. That makes the
// evidence a scripted file diff rather than a photograph of some LEDs, which
// is what the repo rule requires.
//
// TWO MODES, selected by sw[0]:
//   sw[0]=0  SINGLE   one solve per btnC press. Bring-up and UART capture.
//   sw[0]=1  FREERUN  solves back-to-back forever. This is the workload for
//                     the wall-power measurement -- power must be measured
//                     with the datapath busy, not idle.
//
// sw[2:1] selects which operator vector set is loaded (00=L1, 01=Box, 10=L2).
//
// LEDs:
//   led[0]   heartbeat, ~1.5 Hz. If this is dark the clock or reset is wrong
//            and nothing else on the board means anything.
//   led[1]   done pulse stretched to be visible
//   led[2]   PASS  -- last solve matched the golden z, all N lanes
//   led[3]   FAIL  -- last solve mismatched
//   led[11:4] iter_count of the last solve
//   led[15]  UART transmitter busy
//
// CLOCKING. The Basys3 oscillator is 100 MHz; main9_uniform closes at
// 85.4 MHz, so the design CANNOT be clocked directly from it. A clock divider
// is used rather than an MMCM to keep the bring-up dependency-free: sw[3]
// picks /2 (50 MHz, safe for every build) or /1 (100 MHz, WILL FAIL timing,
// present only to demonstrate the failure deliberately). Replace with an MMCM
// at the measured Fmax once bring-up is confirmed.
// ============================================================================
module basys3_wrapper #(
    parameter integer N        = 8,
    parameter integer MAX_ITER = 32
)(
    input  wire        clk100,       // W5, 100 MHz
    input  wire        btnC,         // U18, start (single mode)
    input  wire        btnU,         // T18, synchronous reset
    input  wire [3:0]  sw,           // V17 V16 W16 W17
    output reg  [15:0] led,
    output wire        uart_tx       // A18, RsTx
);
    localparam integer W = `W_MAIN;

    // ---- clock ------------------------------------------------------------
    reg div = 1'b0;
    always @(posedge clk100) div <= ~div;
    wire clk = sw[3] ? clk100 : div;   // sw[3]=0 -> 50 MHz (use this)

    // ---- reset synchroniser ------------------------------------------------
    reg [3:0] rst_sr = 4'hF;
    always @(posedge clk) rst_sr <= {rst_sr[2:0], btnU};
    wire rst_n = ~rst_sr[3];

    // ---- button debounce + edge -------------------------------------------
    reg [19:0] db = 20'd0;
    reg btn_s = 1'b0, btn_q = 1'b0;
    always @(posedge clk) begin
        if (btnC != btn_s) begin db <= 20'd0; btn_s <= btnC; end
        else if (db != 20'hFFFFF) db <= db + 20'd1;
        btn_q <= (db == 20'hFFFFF) ? btn_s : btn_q;
    end
    wire btn_rise = (db == 20'hFFFFF) && btn_s && !btn_q;

    // ---- golden vectors in ROM --------------------------------------------
    // One set per operator. $readmemh on a reg array infers block/distributed
    // ROM at synthesis; the .mem files are the SAME ones the gate-level
    // regression checks against, so hardware and simulation cannot diverge.
    reg [W-1:0] m_rom [0:3*N*N-1];
    reg [W-1:0] q_rom [0:3*N-1];
    reg [W-1:0] z_rom [0:3*N-1];
    initial begin
        $readmemh("M_all.mem", m_rom);
        $readmemh("q_all.mem", q_rom);
        $readmemh("z_all.mem", z_rom);
    end

    wire [1:0] op = (sw[2:1] > 2'd2) ? 2'd0 : sw[2:1];

    reg [(N*N*W)-1:0] weight_bus;
    reg [(N*W)-1:0]   q_bus;
    reg [(N*W)-1:0]   z_gold;
    integer i;
        // If $readmemh fails the ROMs synthesise to zero, the solver "converges"
    // in one iteration, and z_out = 0 == z_gold = 0 reads as PASS. A golden z
    // of all zeros is never legitimate, so flag it instead.
    reg rom_bad;
    always @(*) begin
        rom_bad = 1'b1;
        for (i = 0; i < 3*N; i = i + 1)
            if (z_rom[i] != {W{1'b0}}) rom_bad = 1'b0;
    end
    always @(*) begin
        for (i = 0; i < N*N; i = i + 1)
            weight_bus[(i*W) +: W] = m_rom[op*N*N + i];
        for (i = 0; i < N; i = i + 1) begin
            q_bus[(i*W) +: W]  = q_rom[op*N + i];
            z_gold[(i*W) +: W] = z_rom[op*N + i];
        end
    end

    // ---- DUT ---------------------------------------------------------------
    reg  start = 1'b0;
    wire done;
    wire [7:0] iter_count;
    wire [(N*W)-1:0] z_out;

        // MUST pass these explicitly. admm_top defaults to ASYMMETRIC=1 and
    // USE_DSP_L2=1, neither of which matches any build in the study --
    // run_ooc.tcl passes ASYMMETRIC=0, USE_DSP_L2=0 for every tag. Omitting
    // them silently builds the asymmetric preset (lanes 16/8/7), which zeroes
    // the low 8 bits of Box output and the low 9 of L2, while leaving L1
    // full-width and therefore passing.
    admm_top #(.N(N), .ASYMMETRIC(0), .USE_DSP_L2(0),
               .F_L1_P(`F_MAIN), .F_BOX_P(`F_MAIN), .F_L2_P(`F_MAIN)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .prox_mode(op),
        .max_iter(MAX_ITER[7:0]),
        .eps_pri({W{1'b0}}), .eps_dual({W{1'b0}}),
        .weight_bus(weight_bus), .q_bus(q_bus),
        .done(done), .iter_count(iter_count), .z_out(z_out)
    );

    // ---- compare against golden -------------------------------------------
    reg match;
    integer j;
    always @(*) begin
        match = 1'b1;
        for (j = 0; j < N; j = j + 1)
            if (z_out[(j*W) +: W] !== z_gold[(j*W) +: W]) match = 1'b0;
    end

    // ---- run control -------------------------------------------------------
    // FREERUN restarts immediately on done, giving the sustained activity the
    // wall-power measurement needs.
    localparam S_IDLE = 2'd0, S_RUN = 2'd1, S_SEND = 2'd2, S_GAP = 2'd3;
    reg [1:0] st = S_IDLE;
    reg pass_r = 1'b0;
    reg [7:0] iter_r = 8'd0;
    reg [7:0] gap = 8'd0;
    // 3 bytes per lane: W_MAIN is 18 at F_MAIN=16, so two bytes is not
    // enough. Sign-extend each lane to 24 bits and send low byte first.
    // Separate lane/sub counters avoid a divide-by-3 in the datapath.
    localparam integer BPL = 3;
    reg [3:0] lane_i = 4'd0;
    reg [1:0] sub_i  = 2'd0;
    reg signed [23:0] zext;

    reg  tx_start = 1'b0;
    reg  [7:0] tx_data = 8'd0;
    wire tx_busy;

    always @(posedge clk) begin
        if (!rst_n) begin
            st <= S_IDLE; start <= 1'b0; tx_start <= 1'b0;
            lane_i <= 4'd0; sub_i <= 2'd0;
        end else begin
            start <= 1'b0; tx_start <= 1'b0;
            case (st)
              S_IDLE: if (btn_rise || sw[0]) begin start <= 1'b1; st <= S_RUN; end
              S_RUN:  if (done) begin
                          pass_r <= match; iter_r <= iter_count;
                          lane_i <= 4'd0; sub_i <= 2'd0;
                          st <= sw[0] ? S_GAP : S_SEND;   // freerun skips UART
                      end
              S_SEND: if (!tx_busy && !tx_start) begin
                          if (lane_i < N[3:0]) begin
                              zext = $signed(z_out[(lane_i*W) +: W]);
                              tx_data  <= (sub_i == 2'd0) ? zext[7:0]  :
                                          (sub_i == 2'd1) ? zext[15:8] :
                                                            zext[23:16];
                              tx_start <= 1'b1;
                              if (sub_i == 2'd2) begin
                                  sub_i  <= 2'd0;
                                  lane_i <= lane_i + 4'd1;
                              end else sub_i <= sub_i + 2'd1;
                          end else begin
                              tx_data <= 8'h0A; tx_start <= 1'b1;
                              st <= S_GAP; gap <= 8'd0;
                          end
                      end
              S_GAP:  begin
                          gap <= gap + 8'd1;
                          if (gap == 8'hFF) st <= S_IDLE;
                      end
            endcase
        end
    end

    // ---- status ------------------------------------------------------------
    reg [24:0] hb = 25'd0;
    reg [21:0] stretch = 22'd0;
    always @(posedge clk) begin
        hb <= hb + 25'd1;
        if (done) stretch <= 22'h3FFFFF;
        else if (stretch != 22'd0) stretch <= stretch - 22'd1;
        led <= {tx_busy, rom_bad, 2'b00, iter_r,
                (!pass_r || rom_bad), (pass_r && !rom_bad),
                (stretch != 22'd0), hb[24]};
    end

    uart_tx #(.CLK_HZ(50_000_000), .BAUD(115200)) u_tx (
        .clk(clk), .rst_n(rst_n), .start(tx_start), .data(tx_data),
        .tx(uart_tx), .busy(tx_busy)
    );
endmodule
