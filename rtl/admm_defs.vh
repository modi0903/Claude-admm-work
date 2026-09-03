// ============================================================================
// admm_defs.vh -- Single source of truth for the fixed-point formats.
//
// FORMAT CONVENTION
//   Q(I).(F)  =>  I integer bits INCLUDING the sign bit, F fractional bits.
//                 Total width W = I + F.  Range [-2^(I-1), 2^(I-1) - 2^-F].
//
// ALL LANES SHARE THE SAME INTEGER WIDTH (I = INT_BITS). Lanes differ ONLY in
// the number of fractional bits. This is the whole point: identical dynamic
// range, asymmetric precision. It also means a narrowing cast can never
// overflow the integer field -- it is a pure round-off -- which is what makes
// the wordlength ordering argument clean.
//
//   Main / L1 lane : Q2.16 -> 18 bits   (maps exactly onto DSP48E1 B-port)
//   Box lane       : Q2.8  -> 10 bits
//   L2 lane        : Q2.7  ->  9 bits
// ============================================================================
`ifndef ADMM_DEFS_VH
`define ADMM_DEFS_VH

`define INT_BITS      2

// Main datapath fractional width. Overridable from synthesis with
//   synth_design -verilog_define F_MAIN=9
// so the whole datapath (M, q, accumulator, x, v, z, u, residuals) scales
// together. NOTE: the bit-exact testbench vectors are generated at F_MAIN=16;
// a build at another F_MAIN is NOT covered by that regression.
`ifndef F_MAIN
`define F_MAIN        16
`endif
`define W_MAIN        (`INT_BITS + `F_MAIN)

// Asymmetric lane fractional widths
`define F_BOX_ASYM     8
`define F_L2_ASYM      7

// Systolic accumulator. product of Q2.16 x Q2.16 = Q4.32 (36b).
// Summing N=8 terms needs log2(N)=3 guard bits -> Q7.32. Round up to Q8.32.
`define ACC_INT       8
`define F_ACC         (2 * `F_MAIN)
`define W_ACC         (`ACC_INT + `F_ACC)   // 40 at F_MAIN=16; scales down

// Proximal mode encoding
`define MODE_L1       2'b00
`define MODE_BOX      2'b01
`define MODE_L2       2'b10

`endif
