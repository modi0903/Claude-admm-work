`timescale 1ns / 1ps
// ============================================================================
// sat_shift -- multiply by rho = 2^SH with saturation (SH >= 0) or
// round-to-nearest (SH < 0). Constraining rho to a power of two turns the
// x-update pre-combination into a shift instead of N multipliers. This is a
// real architectural constraint and it interacts with Proposition 1: the
// feasible rho interval must contain a power of two, which is a stronger and
// more honest statement than a continuous bound.
// ============================================================================
module sat_shift #(
    parameter integer W  = 18,
    parameter integer SH = 0            // may be negative
)(
    input  wire signed [W-1:0] din,
    output wire signed [W-1:0] dout
);
    localparam integer ASH  = (SH < 0) ? -SH : SH;
    localparam integer WX   = W + ((SH > 0) ? SH : 0);
    localparam integer RSH1 = (SH < 0 && ASH > 0) ? (ASH - 1) : 0;

    localparam signed [WX:0] MAXV =  (1 <<< (W-1)) - 1;
    localparam signed [WX:0] MINV = -(1 <<< (W-1));

    wire signed [WX:0] ext = {{(WX+1-W){din[W-1]}}, din};
    wire signed [WX:0] scl = (SH > 0) ? (ext <<< ASH)
                           : (SH < 0) ? ((ext + $signed({{WX{1'b0}}, 1'b1} <<< RSH1)) >>> ASH)
                                      :  ext;

    assign dout = (scl > MAXV) ? MAXV[W-1:0] :
                  (scl < MINV) ? MINV[W-1:0] : scl[W-1:0];
endmodule
