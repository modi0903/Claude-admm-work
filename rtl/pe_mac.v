`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// pe_mac -- weight-stationary MAC.
//
// 18 x 18 signed multiply maps directly onto a single DSP48E1 (25x18 signed
// multiplier, 48-bit P accumulator). W_MAIN = 18 is not an arbitrary choice:
// it is the widest operand the DSP48E1 B port takes for free. Going to 19 bits
// would cost a second DSP per PE.
//
// The multiplier and the adder are in the SAME always block feeding one
// register, so Vivado infers MREG=0 / PREG=1. If timing needs it, split into
// two pipeline stages (MREG=1) and add 1 to the array latency.
// ============================================================================
module pe_mac (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          load_w,
    input  wire signed [`W_MAIN-1:0]     weight_in,
    input  wire signed [`W_MAIN-1:0]     x_in,
    input  wire signed [`W_ACC-1:0]      psum_in,
    output reg  signed [`W_MAIN-1:0]     x_out,
    output reg  signed [`W_ACC-1:0]      psum_out
);
    reg signed [`W_MAIN-1:0] weight_reg;

    // Q2.16 * Q2.16 = Q4.32 (36 bits), sign-extended into the Q8.32 accumulator.
    wire signed [(2*`W_MAIN)-1:0] prod = weight_reg * x_in;
    wire signed [`W_ACC-1:0] prod_ext =
        {{(`W_ACC - 2*`W_MAIN){prod[(2*`W_MAIN)-1]}}, prod};

    always @(posedge clk) begin
        if (!rst_n) begin
            weight_reg <= {`W_MAIN{1'b0}};
            x_out      <= {`W_MAIN{1'b0}};
            psum_out   <= {`W_ACC{1'b0}};
        end else begin
            if (load_w) weight_reg <= weight_in;
            x_out    <= x_in;
            psum_out <= prod_ext + psum_in;
        end
    end
endmodule
