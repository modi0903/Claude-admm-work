`timescale 1ns / 1ps
// ============================================================================
// tb_admm_top_gl -- gate-level twin of tb_admm_top, for post-route simulation.
//
// Differences from tb_admm_top.v, all forced by the netlist:
//   * The DUT is instantiated with NO parameter overrides. A post-route
//     netlist has no parameters; overriding them is an elaboration error.
//     N / ASYMMETRIC / F_MAIN are baked into the checkpoint, so they are
//     passed to the TESTBENCH only, and only to pick vector files and size
//     the buses. They MUST match the build being simulated.
//   * `include "admm_defs.vh" is gone -- W is computed from FM instead, so
//     this file compiles with no include path.
//   * Start-to-done cycles are counted and printed. That is the throughput
//     number TODO P1 needs, and this is the only place it can be measured
//     honestly (post-route, real FSM, real vectors).
//
// Vectors must have been generated at the SAME F_MAIN as the build:
//     python model/gen_vectors_fm.py 9      # for a main9_* build
// Note that script OVERWRITES tb/vectors/*_unif.mem. Back them up first --
// the committed set is F_MAIN=16 and the iverilog regression depends on it.
// ============================================================================
// Configuration arrives as `define macros (xvlog -d FM=16 -d ASYM=0), NOT as
// xelab -generic_top. -generic_top renames the elaborated top to the ESCAPED
// identifier \tb_admm_top_gl(FM=16) , which:
//   * makes /tb_admm_top_gl/dut unresolvable as a scope path,
//   * writes parentheses into SAIF instance names, which Vivado's own SAIF
//     parser then rejects ("syntax error, unexpected WORD"), and
//   * breaks read_saif -strip_path.
// Macros keep the top named plainly and all three problems disappear.
`ifndef FM
  `define FM 16
`endif
`ifndef ASYM
  `define ASYM 0
`endif

module tb_admm_top_gl;

    localparam integer N          = 8;
    localparam integer FM         = `FM;    // MUST match the build's F_MAIN
    localparam integer ASYMMETRIC = `ASYM;  // MUST match the build's generic
    localparam integer MAX_ITER   = 32;

    localparam integer INT_BITS = 2;            // admm_defs.vh
    localparam integer W        = INT_BITS + FM;

    reg clk = 0, rst_n = 0, start = 0;
    reg [1:0] prox_mode = 2'b00;
    wire done;
    wire [7:0] iter_count;
    wire [(N*W)-1:0] z_out;

    reg [(N*N*W)-1:0] weight_bus;
    reg [(N*W)-1:0]   q_bus;

    reg [W-1:0] m_mem [0:N*N-1];
    reg [W-1:0] q_mem [0:N-1];
    reg [W-1:0] z_exp [0:N-1];

    integer i, errors, case_err;
    integer cyc_start, cyc_now, cyc_total, cases, iter_total;
    reg [255:0] tag;

    // 20 ns period = the 50 MHz OOC constraint in run_ooc.tcl. If a different
    // period is being characterised, change this to match or the SAIF is
    // measuring activity at the wrong clock.
    always #10 clk = ~clk;

    // Free-running cycle counter, used for the throughput measurement.
    always @(posedge clk) cyc_now <= cyc_now + 1;

    // No parameter overrides -- see header.
    admm_top dut (
        .clk(clk), .rst_n(rst_n), .start(start), .prox_mode(prox_mode),
        .max_iter(MAX_ITER[7:0]),
        .eps_pri({W{1'b0}}), .eps_dual({W{1'b0}}),
        .weight_bus(weight_bus), .q_bus(q_bus),
        .done(done), .iter_count(iter_count), .z_out(z_out)
    );

    // Filenames are passed in as literals rather than built with $sformatf.
    // $sformatf is SystemVerilog; xvlog defaults to Verilog-2001 and rejects
    // it. Passing literals keeps this file compilable in either dialect and
    // under iverilog too.
    task load_and_run;
        input [255:0] name;
        input [1:0]   mode;
        input [8*40-1:0] pM, pQ, pZ;
        integer c0;
        begin
            tag = name;
            $readmemh(pM, m_mem);
            $readmemh(pQ, q_mem);
            $readmemh(pZ, z_exp);
            for (i = 0; i < N*N; i = i + 1) weight_bus[(i*W) +: W] = m_mem[i];
            for (i = 0; i < N;   i = i + 1) q_bus[(i*W) +: W]      = q_mem[i];
            case_err = 0;
            prox_mode = mode;
            @(negedge clk); start = 1; c0 = cyc_now;
            @(negedge clk); start = 0;
            wait (done);
            @(negedge clk);
            cyc_total  = cyc_total + (cyc_now - c0);
            iter_total = iter_total + iter_count;   // ACTUAL, not MAX_ITER
            cases      = cases + 1;
            for (i = 0; i < N; i = i + 1) begin
                if (z_out[(i*W) +: W] !== z_exp[i]) begin
                    errors = errors + 1; case_err = case_err + 1;
                    $display("  MISMATCH %0s z[%0d]: rtl=%0d golden=%0d",
                             name, i, $signed(z_out[(i*W) +: W]),
                             $signed(z_exp[i]));
                end
            end
            $display("  %0s : iters=%0d  cycles=%0d  %s",
                     name, iter_count, (cyc_now - c0),
                     (case_err == 0) ? "OK" : "FAIL");
        end
    endtask

    initial begin
        errors = 0; cyc_total = 0; cases = 0; cyc_now = 0; iter_total = 0;
        repeat (8) @(posedge clk);          // longer than RTL tb: GSR release
        rst_n = 1;
        repeat (4) @(posedge clk);

        $display("GATE-LEVEL  N=%0d  F_MAIN=%0d  W=%0d  ASYMMETRIC=%0d",
                 N, FM, W, ASYMMETRIC);

        if (ASYMMETRIC == 0) begin
            load_and_run("l1_unif",  2'b00, "tb/vectors/M_l1_unif.mem",
                         "tb/vectors/q_l1_unif.mem", "tb/vectors/z_l1_unif.mem");
            load_and_run("box_unif", 2'b01, "tb/vectors/M_box_unif.mem",
                         "tb/vectors/q_box_unif.mem", "tb/vectors/z_box_unif.mem");
            load_and_run("l2_unif",  2'b10, "tb/vectors/M_l2_unif.mem",
                         "tb/vectors/q_l2_unif.mem", "tb/vectors/z_l2_unif.mem");
        end else begin
            load_and_run("l1_asym",  2'b00, "tb/vectors/M_l1_asym.mem",
                         "tb/vectors/q_l1_asym.mem", "tb/vectors/z_l1_asym.mem");
            load_and_run("box_asym", 2'b01, "tb/vectors/M_box_asym.mem",
                         "tb/vectors/q_box_asym.mem", "tb/vectors/z_box_asym.mem");
            load_and_run("l2_asym",  2'b10, "tb/vectors/M_l2_asym.mem",
                         "tb/vectors/q_l2_asym.mem", "tb/vectors/z_l2_asym.mem");
        end

        $display("");
        // Divide by ACTUAL iterations, not MAX_ITER. With eps=0 the residual
        // reaches exactly zero at bit-exact convergence, so the early-exit
        // DOES fire and iteration count is data-dependent. Dividing by
        // MAX_ITER understates cycles/iteration by roughly 2x.
        $display("THROUGHPUT: %0d cycles over %0d solves, %0d iterations total",
                 cyc_total, cases, iter_total);
        $display("THROUGHPUT: %0d cycles/iteration (averaged over actual iters)",
                 cyc_total/iter_total);
        $display("  cycles/solve is DATA-DEPENDENT (early exit fires) -- quote");
        $display("  the per-case cycles above, or cycles = c/iter * K + overhead.");
        $display("  -> solutions/s = Fmax / (cycles/solve); use the Fmax the");
        $display("     sweep actually closed at, not the 50 MHz sim clock.");

        if (errors == 0) $display("PASS: all lanes bit-exact vs golden model");
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end

    initial begin
        #20000000;
        $display("FAIL: timeout");
        $finish;
    end
endmodule
