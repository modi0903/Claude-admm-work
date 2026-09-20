`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// tb_admm_top -- self-checking against the bit-exact Python golden model.
// Runs a fixed MAX_ITER (eps = 0 so early exit never fires) and compares the
// final z vector element by element. Any mismatch is a hard failure.
// ============================================================================
module tb_admm_top;
    parameter integer N          = 8;
    parameter integer ASYMMETRIC = 1;
    parameter integer MAX_ITER   = 32;

    localparam integer W = `W_MAIN;

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
    reg [255:0] tag;

    always #5 clk = ~clk;

    admm_top #(.N(N), .ASYMMETRIC(ASYMMETRIC), .RHO_SHIFT(0)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .prox_mode(prox_mode),
        .max_iter(MAX_ITER[7:0]),
        .eps_pri({W{1'b0}}), .eps_dual({W{1'b0}}),
        .weight_bus(weight_bus), .q_bus(q_bus),
        .done(done), .iter_count(iter_count), .z_out(z_out)
    );

    task load_and_run;
        input [255:0] name;
        input [1:0]   mode;
        begin
            tag = name;
            $readmemh($sformatf("tb/vectors/M_%0s.mem", name), m_mem);
            $readmemh($sformatf("tb/vectors/q_%0s.mem", name), q_mem);
            $readmemh($sformatf("tb/vectors/z_%0s.mem", name), z_exp);
            for (i = 0; i < N*N; i = i + 1) weight_bus[(i*W) +: W] = m_mem[i];
            for (i = 0; i < N;   i = i + 1) q_bus[(i*W) +: W]      = q_mem[i];
            case_err = 0;
            prox_mode = mode;
            @(negedge clk); start = 1;
            @(negedge clk); start = 0;
            wait (done);
            @(negedge clk);
            for (i = 0; i < N; i = i + 1) begin
                if (z_out[(i*W) +: W] !== z_exp[i]) begin
                    errors = errors + 1; case_err = case_err + 1;
                    $display("  MISMATCH %0s z[%0d]: rtl=%0d golden=%0d",
                             name, i, $signed(z_out[(i*W) +: W]), $signed(z_exp[i]));
                end
            end
            $display("  %0s : iters=%0d  %s", name, iter_count,
                     (case_err == 0) ? "OK" : "FAIL");
        end
    endtask

    initial begin
        errors = 0;
        repeat (4) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);

        $display("ASYMMETRIC=%0d", ASYMMETRIC);
        if (ASYMMETRIC == 0) begin
`ifdef LASSO   // second problem: model/gen_vectors_lasso.py, iverilog -DLASSO
            load_and_run("l1_lasso0", `MODE_L1);
            load_and_run("l1_lasso1", `MODE_L1);
            load_and_run("l1_lasso2", `MODE_L1);
`else
            load_and_run("l1_unif",  `MODE_L1);
            load_and_run("box_unif", `MODE_BOX);
            load_and_run("l2_unif",  `MODE_L2);
`endif
        end else begin
            load_and_run("l1_asym",  `MODE_L1);
            load_and_run("box_asym", `MODE_BOX);
            load_and_run("l2_asym",  `MODE_L2);
        end

        if (errors == 0) $display("PASS: all lanes bit-exact vs golden model");
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end

    initial begin
        #2000000;
        $display("FAIL: timeout");
        $finish;
    end
endmodule
