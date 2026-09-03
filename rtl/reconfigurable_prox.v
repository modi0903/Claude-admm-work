`timescale 1ns / 1ps
`include "admm_defs.vh"
// ============================================================================
// reconfigurable_prox
//
// Three proximal operators sharing one input port and one output mux.
//   L1  : soft-threshold   S_kappa(v) = sgn(v) max(|v|-kappa, 0)     Q2.16
//   Box : projection       P_C(v)     = min(max(v,lo),hi)            Q2.8
//   L2  : ridge scaling    z          = gamma * v,  gamma=rho/(rho+lam)  Q2.7
//
// ASYMMETRIC = 0 -> all three lanes at F_MAIN (the uniform baseline)
// ASYMMETRIC = 1 -> Box at F_BOX_ASYM, L2 at F_L2_ASYM
//
// The two builds differ by THIS PARAMETER ONLY. Same file, same top, same
// constraints. That is what makes the area comparison defensible.
//
// prox_mode is a runtime input, NOT a parameter. All three lanes are
// physically instantiated and the mux selects per phase. If prox_mode were
// tied off at elaboration the synthesiser would delete two lanes and the
// reported saving would be meaningless.
//
// Constants are re-derived from the Q2.16 specification via q_narrow_const().
// They are NOT bit-sliced. GAMMA_Q16 = 32768 (0.5) sliced to 9 bits is 0, and
// a lane that multiplies by zero synthesises to nothing -- which is exactly
// the kind of artefact that produces a spectacular fake area reduction.
// ============================================================================
module reconfigurable_prox #(
    parameter integer ASYMMETRIC = 1,
    parameter integer F_L1_P  = -1,   // -1 = use ASYMMETRIC preset
    parameter integer F_BOX_P = -1,
    parameter integer F_L2_P  = -1,

    // 1 = let Vivado infer a DSP48E1 for the L2 gamma multiply
    // 0 = force it into fabric.
    // Vivado infers a DSP by OPERAND WIDTH: an 18x18 clears the threshold, a
    // 9x9 does not. So a naive uniform-vs-asymmetric comparison confounds
    // "narrower is smaller" with "narrow fell off the hard macro". Building
    // both widths with USE_DSP_L2=0 removes that confound and is the only
    // honest wordlength comparison on a DSP-bearing device.
    parameter integer USE_DSP_L2 = 1,

    // Algorithm constants, specified once in Q2.16.
    parameter integer KAPPA_Q16   = 32'sd6554,   //  0.100  (L1 threshold, lam/rho)
    parameter integer BOX_HI_Q16  = 32'sd65536,  //  1.000  (DAC upper clip)
    parameter integer BOX_LO_Q16  = -32'sd65536, // -1.000  (DAC lower clip)
    parameter integer GAMMA_Q16   = 32'sd43691   //  0.667  = rho/(rho+lam)
)(
    input  wire                            clk,
    input  wire                            rst_n,
    input  wire                            en,
    input  wire [1:0]                      prox_mode,
    input  wire signed [`W_MAIN-1:0]       v_in,
    output reg  signed [`W_MAIN-1:0]       z_out
);
    // ---------------------------------------------------------------------
    // Elaboration-time constant narrowing: round-half-up by `sh` fractional
    // bits. Constants are RE-DERIVED, never bit-sliced. GAMMA_Q16=43691
    // sliced to 9 bits is 43691 & 511 = 171 (i.e. 1.34, not 0.667); a Q15
    // gamma of 32768 sliced to 9 bits is exactly 0, and a lane that
    // multiplies by zero synthesises away -- which is how you manufacture a
    // spectacular fake area reduction.
    // ---------------------------------------------------------------------
    function integer q_narrow_const;
        input integer v;
        input integer sh;
        begin
            if (sh <= 0) q_narrow_const = v;
            else         q_narrow_const = (v + (1 << (sh-1))) >>> sh;
        end
    endfunction

    // ---------------------------------------------------------------------
    // Lane geometry
    // ---------------------------------------------------------------------
    // Explicit per-lane widths override the ASYMMETRIC preset when >= 0.
    // Lets synthesis sweep an arbitrary triple instead of one binary switch.
    localparam integer F_L1  = (F_L1_P  >= 0) ? F_L1_P  : `F_MAIN;
    localparam integer F_BOX = (F_BOX_P >= 0) ? F_BOX_P :
                               ((ASYMMETRIC != 0) ? `F_BOX_ASYM : `F_MAIN);
    localparam integer F_L2  = (F_L2_P  >= 0) ? F_L2_P  :
                               ((ASYMMETRIC != 0) ? `F_L2_ASYM  : `F_MAIN);

    localparam integer W_L1  = `INT_BITS + F_L1;
    localparam integer W_BOX = `INT_BITS + F_BOX;
    localparam integer W_L2  = `INT_BITS + F_L2;

    // ---------------------------------------------------------------------
    // Lane constants, re-derived (rounded), never sliced
    // ---------------------------------------------------------------------
    // The *_Q16 parameters are specified in Q2.16 ALWAYS, independently of
    // F_MAIN. Narrowing them by (F_MAIN - F_lane) is only correct when
    // F_MAIN == 16; at F_MAIN=9 the shift is zero and the raw Q2.16 constant
    // lands in an 11-bit lane (kappa 6554 vs a limit of 1023), saturating all
    // three constants to garbage. Narrow from the SPEC format, not from the
    // datapath format.
    localparam integer SPEC_FRAC = 16;
    localparam integer KAPPA_L1  = q_narrow_const(KAPPA_Q16,  SPEC_FRAC - F_L1 );
    localparam integer BOX_HI    = q_narrow_const(BOX_HI_Q16, SPEC_FRAC - F_BOX);
    localparam integer BOX_LO    = q_narrow_const(BOX_LO_Q16, SPEC_FRAC - F_BOX);
    localparam integer GAMMA_L2  = q_narrow_const(GAMMA_Q16,  SPEC_FRAC - F_L2 );

    // =====================================================================
    // LANE 1 : L1 soft-threshold, full Q2.16
    // =====================================================================
    wire signed [W_L1-1:0] v_l1;
    q_narrow #(.W_IN(`W_MAIN), .F_IN(`F_MAIN), .W_OUT(W_L1), .F_OUT(F_L1))
        u_cast_l1 (.din(v_in), .dout(v_l1));
    // Guard the -2^(W-1) negation corner case.
    wire l1_is_min = (v_l1 == {1'b1, {(W_L1-1){1'b0}}});
    wire signed [W_L1-1:0] abs_v = l1_is_min ? {1'b0, {(W_L1-1){1'b1}}}
                                             : (v_l1[W_L1-1] ? -v_l1 : v_l1);
    // NOTE: a part-select of a localparam is ALWAYS UNSIGNED in Verilog.
    // Every comparison against a lane constant must go through $signed() or
    // the whole expression silently becomes an unsigned compare and negative
    // samples read as large positives.
    wire signed [W_L1-1:0] sub_v = abs_v - $signed(KAPPA_L1[W_L1-1:0]);
    wire signed [W_L1-1:0] l1_mag = (sub_v > 0) ? sub_v : {W_L1{1'b0}};
    wire signed [W_L1-1:0] l1_res = v_l1[W_L1-1] ? -l1_mag : l1_mag;

    wire signed [`W_MAIN-1:0] l1_res_wide;
    q_widen #(.W_IN(W_L1), .F_IN(F_L1), .W_OUT(`W_MAIN), .F_OUT(`F_MAIN))
        u_widen_l1 (.din(l1_res), .dout(l1_res_wide));

    // =====================================================================
    // LANE 2 : Box projection, Q2.8 when ASYMMETRIC
    // =====================================================================
    wire signed [W_BOX-1:0] v_box;
    q_narrow #(.W_IN(`W_MAIN), .F_IN(`F_MAIN), .W_OUT(W_BOX), .F_OUT(F_BOX))
        u_cast_box (.din(v_in), .dout(v_box));

    wire signed [W_BOX-1:0] box_hi_s = $signed(BOX_HI[W_BOX-1:0]);
    wire signed [W_BOX-1:0] box_lo_s = $signed(BOX_LO[W_BOX-1:0]);
    wire signed [W_BOX-1:0] box_res  = (v_box > box_hi_s) ? box_hi_s :
                                       (v_box < box_lo_s) ? box_lo_s : v_box;

    wire signed [`W_MAIN-1:0] box_res_wide;
    q_widen #(.W_IN(W_BOX), .F_IN(F_BOX), .W_OUT(`W_MAIN), .F_OUT(`F_MAIN))
        u_widen_box (.din(box_res), .dout(box_res_wide));

    // =====================================================================
    // LANE 3 : L2 ridge scaling, Q2.7 when ASYMMETRIC
    // =====================================================================
    wire signed [W_L2-1:0] v_l2;
    q_narrow #(.W_IN(`W_MAIN), .F_IN(`F_MAIN), .W_OUT(W_L2), .F_OUT(F_L2))
        u_cast_l2 (.din(v_in), .dout(v_l2));

    // Q(I).(F_L2) * Q(I).(F_L2) = Q(2I).(2*F_L2)
    wire signed [W_L2-1:0]     gamma_s = $signed(GAMMA_L2[W_L2-1:0]);
    wire signed [(2*W_L2)-1:0] l2_prod;
    generate
        if (USE_DSP_L2 != 0) begin : G_L2_DSP
            (* use_dsp = "yes" *) wire signed [(2*W_L2)-1:0] p;
            assign p = v_l2 * gamma_s;
            assign l2_prod = p;
        end else begin : G_L2_LUT
            (* use_dsp = "no" *) wire signed [(2*W_L2)-1:0] p;
            assign p = v_l2 * gamma_s;
            assign l2_prod = p;
        end
    endgenerate

    wire signed [W_L2-1:0] l2_res;
    q_narrow #(.W_IN(2*W_L2), .F_IN(2*F_L2), .W_OUT(W_L2), .F_OUT(F_L2))
        u_cast_l2_out (.din(l2_prod), .dout(l2_res));

    wire signed [`W_MAIN-1:0] l2_res_wide;
    q_widen #(.W_IN(W_L2), .F_IN(F_L2), .W_OUT(`W_MAIN), .F_OUT(`F_MAIN))
        u_widen_l2 (.din(l2_res), .dout(l2_res_wide));

    // =====================================================================
    // Registered output mux
    // =====================================================================
    always @(posedge clk) begin
        if (!rst_n) begin
            z_out <= {`W_MAIN{1'b0}};
        end else if (en) begin
            case (prox_mode)
                `MODE_L1  : z_out <= l1_res_wide;
                `MODE_BOX : z_out <= box_res_wide;
                `MODE_L2  : z_out <= l2_res_wide;
                default   : z_out <= {`W_MAIN{1'b0}};
            endcase
        end
    end
endmodule
