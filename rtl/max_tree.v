`timescale 1ns / 1ps
// ============================================================================
// max_tree -- balanced binary maximum reduction over N unsigned magnitudes.
//
// Replaces a `for` loop inside always @*, which synthesises as N SERIAL
// compare-mux stages. At N=8, 18 bits, that chain plus the saturating
// subtract feeding it was a -18.96 ns path to converged_reg on an 8 ns clock.
// Depth here is ceil(log2(N)) = 3 instead of 8.
// ============================================================================
module max_tree #(
    parameter integer W = 18,
    parameter integer N = 8
)(
    input  wire [(N*W)-1:0] din,      // non-negative magnitudes
    output wire [W-1:0]     dout
);
    localparam integer LVLS = (N <= 1) ? 1 : $clog2(N);
    localparam integer NP   = 1 << LVLS;

    wire [W-1:0] lvl [0:LVLS][0:NP-1];

    genvar i, l;
    generate
        for (i = 0; i < NP; i = i + 1) begin : G_IN
            if (i < N) assign lvl[0][i] = din[(i*W) +: W];
            else       assign lvl[0][i] = {W{1'b0}};
        end
        for (l = 0; l < LVLS; l = l + 1) begin : G_LVL
            for (i = 0; i < (NP >> (l+1)); i = i + 1) begin : G_NODE
                assign lvl[l+1][i] = (lvl[l][2*i] > lvl[l][2*i+1])
                                   ?  lvl[l][2*i] : lvl[l][2*i+1];
            end
        end
    endgenerate

    assign dout = lvl[LVLS][0];
endmodule
