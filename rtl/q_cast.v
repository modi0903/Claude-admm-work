`timescale 1ns / 1ps
// ============================================================================
// q_narrow : Q(I_IN).(F_IN) -> Q(I_OUT).(F_OUT)
//
// Round-half-up on the discarded fractional bits, then SATURATE on the integer
// field. This replaces the bit-slice `v_in[W-1:0]`, which is a modulo-2^W
// wraparound, not a precision reduction, and which silently turns a large
// positive sample into a small negative one.
//
// Combinational. Depth: one CPA + one compare. Registered by the caller.
// ============================================================================
module q_narrow #(
    parameter integer W_IN  = 18,
    parameter integer F_IN  = 16,
    parameter integer W_OUT = 10,
    parameter integer F_OUT = 8
)(
    input  wire signed [W_IN-1:0]  din,
    output wire signed [W_OUT-1:0] dout
);
    localparam integer SH    = F_IN - F_OUT;          // >= 0
    localparam integer SHM1  = (SH > 0) ? (SH - 1) : 0;
    localparam integer WX    = W_IN + 1;              // rounding headroom

    localparam signed [WX-1:0] MAXV =  (1 <<< (W_OUT-1)) - 1;
    localparam signed [WX-1:0] MINV = -(1 <<< (W_OUT-1));

    wire signed [WX-1:0] ext = {din[W_IN-1], din};
    wire signed [WX-1:0] rnd = (SH == 0) ? ext
                                         : ext + $signed({{(WX-1){1'b0}}, 1'b1} <<< SHM1);
    wire signed [WX-1:0] shf = rnd >>> SH;

    assign dout = (shf > MAXV) ? MAXV[W_OUT-1:0] :
                  (shf < MINV) ? MINV[W_OUT-1:0] :
                                 shf[W_OUT-1:0];
endmodule


// ============================================================================
// q_widen : Q(I_IN).(F_IN) -> Q(I_OUT).(F_OUT) with F_OUT >= F_IN.
// Sign-extend then left-shift. Exact, no loss, no saturation possible when
// I_OUT >= I_IN.
// ============================================================================
module q_widen #(
    parameter integer W_IN  = 10,
    parameter integer F_IN  = 8,
    parameter integer W_OUT = 18,
    parameter integer F_OUT = 16
)(
    input  wire signed [W_IN-1:0]  din,
    output wire signed [W_OUT-1:0] dout
);
    localparam integer SH = F_OUT - F_IN;             // >= 0
    wire signed [W_OUT-1:0] ext = {{(W_OUT-W_IN){din[W_IN-1]}}, din};
    assign dout = ext <<< SH;
endmodule


// ============================================================================
// sat_add : saturating signed add on W bits (no wraparound in the dual update
// or the pre-combine). Wraparound in u^k is how an ADMM accelerator diverges
// silently instead of loudly.
// ============================================================================
module sat_add #(
    parameter integer W = 18
)(
    input  wire signed [W-1:0] a,
    input  wire signed [W-1:0] b,
    input  wire                sub,   // 1 => a - b
    output wire signed [W-1:0] y
);
    wire signed [W:0] bb  = sub ? -{b[W-1], b} : {b[W-1], b};
    wire signed [W:0] sum = {a[W-1], a} + bb;

    localparam signed [W:0] MAXV =  (1 <<< (W-1)) - 1;
    localparam signed [W:0] MINV = -(1 <<< (W-1));

    assign y = (sum > MAXV) ? MAXV[W-1:0] :
               (sum < MINV) ? MINV[W-1:0] : sum[W-1:0];
endmodule
