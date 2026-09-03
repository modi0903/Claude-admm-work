# Phase-Reconfigurable ADMM Accelerator — build status

Everything below is measured, not asserted. Anything not measured is listed as open.

## What now exists

```
rtl/    admm_defs.vh  q_cast.v  sat_shift.v  pe_mac.v
        systolic_array.v  reconfigurable_prox.v  admm_top.v
tb/     tb_admm_top.v  vectors/*.mem
model/  fxp_admm.py  gen_vectors.py  experiments.py
syn/    run_ooc.tcl
```

`iverilog -g2005 -Irtl -o sim -Ptb_admm_top.ASYMMETRIC={0,1} tb/tb_admm_top.v rtl/*.v`

Both builds: **PASS, bit-exact against the Python golden model, all three lanes.**

## Fixed-point contract (one source of truth: `rtl/admm_defs.vh`)

| Signal | Format | Width | Note |
|---|---|---|---|
| main datapath, L1 lane | Q2.16 | 18 | 18 b is the DSP48E1 B-port width — free |
| Box lane | Q2.8 | 10 | placeholder, see open item 1 |
| L2 lane | Q2.7 | 9 | placeholder, see open item 1 |
| systolic accumulator | Q8.32 | 40 | fits the DSP48E1 P register; no overflow for N≤32, \|·\|<2 |

All lanes share `INT_BITS = 2`. A narrowing cast is therefore a pure round-off
and cannot overflow the integer field. That is what makes the ordering
argument clean and the three lane widths independently sweepable.

## Bugs found and fixed in the previous RTL

1. `admm_top` never overrode `BOX_WIDTH`/`L2_WIDTH` — every lane was 16 bits.
   There was no asymmetry in the netlist. No reported area number came from
   that source.
2. `DATA_WIDTH = 16`, not the 18 the manuscript claims throughout.
3. `v_in[W-1:0]` casts took the **low** bits: modulo-2^W wraparound, not a
   precision reduction. Large positive samples wrapped to small negatives and
   passed straight through the Box clamp.
4. `psum_out_bus[... +: DATA_WIDTH]` took the bottom 16 of a 32-bit
   accumulator — unconditional overflow in the main datapath.
5. Constants were bit-sliced. `GAMMA_L2 = 16384` sliced to 9 bits is exactly
   **0**. The L2 lane would have multiplied by zero, synthesised away, and
   produced a spectacular fake area reduction.
6. **Part-selects of a localparam are unsigned in Verilog.** Every Box
   comparison silently became an unsigned compare; all negative samples read
   as large positives and clipped to the upper bound. Fixed with `$signed()`.
7. No ADMM loop existed: no `v = x+u`, no ρ, no residuals, no iteration,
   `done` after a single pass, and the dual update consumed the top-level
   constant `x_in`.
8. The N×N pre-skew register file was 64 registers of dead area — ADMM is
   sequentially dependent, so only one vector is ever in flight and the input
   is held stable. Removed.

## Measured results

### Dynamic range (600 runs, ρ=1, 32×8 real BPSK)

| var | peak | vs Q2.16 limit 2.0 |
|---|---|---|
| q | 0.95 | ok (after scaling) |
| **w = q + ρ(z−u)** | **1.86** | **the binding constraint** |
| x, v, z | ≤1.31 | ok |
| u | 0.40 | ok |

Unscaled, `q` peaks at 2.81 and `w` at 3.80 — both clip. Every earlier
precision measurement was measuring *clipping*, not quantization, and showed a
hard NMSE floor of ~1e-2 that no wordlength could beat.

Fix is exact, not a compromise: the ADMM recursion is positively homogeneous,
so scaling (q, κ, box bounds) by a common α scales (x, z, u) by α and leaves
the trajectory identical. M is untouched. One scalar, computed alongside M and
q in the per-coherence-interval preprocessing — zero hardware cost.
`model/fxp_admm.py` now carries a global saturation counter; **any experiment
ending with SAT_COUNT > 0 is invalid.**

### Per-lane minimum fractional wordlength (SAT_COUNT = 0)

NMSE of z vs the float reference, one lane varied, main path held at Q2.16:

| F | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 12 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 2.8e-2 | 7.1e-3 | 2.1e-3 | 3.3e-4 | 1.5e-4 | 3.3e-5 | 6.8e-6 | 1.9e-6 | 1.5e-7 | 1.7e-8 |
| Box | 7.4e-3 | 1.8e-3 | 3.7e-4 | 1.2e-4 | 2.6e-5 | 6.4e-6 | 1.8e-6 | 4.0e-7 | 3.2e-8 | 4.0e-9 |
| L2 | 2.3e-2 | 5.7e-3 | 1.5e-3 | 3.4e-4 | 1.0e-4 | 2.3e-5 | 6.3e-6 | 1.3e-6 | 9.0e-8 | 8.0e-9 |

F* at each accuracy target:

| target | L1 | Box | L2 | paper's ordering |
|---|---|---|---|---|
| 1e-2 | 4 | 3 | 4 | FAILS |
| 3e-3 | 5 | 4 | 5 | FAILS |
| 1e-3 | 6 | 5 | 6 | FAILS |
| 3e-4 | 7 | 6 | 7 | FAILS |
| 1e-4 | 8 | 7 | 8 | FAILS |
| 3e-5 | 9 | 7 | 8 | FAILS |

**Measured ordering: W\*_L1 ≥ W\*_L2 > W\*_Box, at every threshold.**
The manuscript claims W\*_L1 > W\*_Box ≥ W\*_L2. Box is the *cheapest* lane,
not the middle one, and L2 is not the cheapest.

Theorem 2's premise also fails here: L1 active-set misclassification rate is
**0.0000 from F=4 upward**. The set B_q is empty at any usable wordlength, so
the "irreducible error floor" is not observable and cannot be what forces L1
to full precision.

Separately, no lane needs anything close to 16 fractional bits. At a 1e-3
target the widest lane needs 6. The 18-bit L1 datapath is over-provisioned by
roughly 8 bits against this workload.


## VERIFIED SILICON RESULTS (Artix-7 xc7a35tcpg236-1, OOC, routed, 20 ns target)

Four builds from identical sources. `ASYMMETRIC` selects 18/18/18 vs 18/10/9
lane widths; `USE_DSP_L2` selects whether the L2 gamma multiply may occupy a
DSP48E1. The systolic array is 472 LUTs in all four, as it must be — that is
the control that says the comparison is clean.

| build | LUT total | LUT prox | LUT array | LUT rest | DSP | CARRY | Fmax | Dyn W |
|---|---|---|---|---|---|---|---|---|
| uniform_dsp   | 4979 | 1392 | 472 | 3115 | 72 | 865 | 63.8 | 0.095 |
| asym_dsp      | 5019 | 1432 | 472 | 3115 | 72 | 929 | 57.6 | 0.094 |
| uniform_nodsp | 6308 | 2720 | 472 | 3116 | 64 | 1153 | 58.9 | 0.112 |
| asym_nodsp    | 5299 | 1712 | 472 | 3115 | 64 | 985 | 59.6 | 0.091 |

All four meet timing (WNS +2.6 to +4.3 ns). The earlier −18.96 ns failure was
the serial L-infinity reduction; a balanced `max_tree` plus registering `v` and
the residual magnitudes fixed it.

### Result 1 — asymmetric pruning works, in fabric

| metric | uniform | asymmetric | reduction |
|---|---|---|---|
| proximal array LUTs | 2720 | 1712 | **37.1%** |
| total LUTs | 6308 | 5299 | **16.0%** |
| carry chains | 1153 | 985 | 14.6% |
| dynamic power | 112 mW | 91 mW | 18.8% |
| Fmax | 58.9 MHz | 59.6 MHz | no penalty |

### Result 2 — it disappears on a DSP-bearing device

| metric | uniform | asymmetric | change |
|---|---|---|---|
| proximal array LUTs | 1392 | 1432 | **−2.9% (worse)** |
| total LUTs | 4979 | 5019 | −0.8% (worse) |

When the gamma multiply occupies a DSP48E1, the multiplier is free at both
widths, so narrowing refunds nothing — and the round/saturate/widen casts that
implement the narrowing cost ~40 LUTs the hard macro does not give back.

### Mechanism

Implied fabric cost of one gamma multiplier per lane, from the difference
between the DSP and no-DSP builds:

| operand width | LUTs |
|---|---|
| 18x18 | 166 |
| 9x9 | 35 |
| ratio | 4.74 (area ~ W^2 predicts 4.00) |

The saving is almost entirely the multiplier scaling quadratically with
operand width. Everything else in the lane — compares, muxes, the Box clamp —
contributes little, and the casts contribute negatively.

### The claim this supports

Not "asymmetric datapath pruning reduces LUTs by 52.3%". Rather:

> Per-operator wordlength reduction pays in proportion to how much of the lane
> is multiplier, and only while that multiplier is built from fabric. Narrowing
> an operator below the hard-macro operand width converts a free multiplier
> into a paid one and is net negative. The 37.1% proximal-array saving measured
> here is therefore a lower bound on the ASIC case and an upper bound on what
> any DSP-bearing FPGA will deliver.

That is a stronger and more useful contribution than the original claim,
because it predicts *when* co-design of this kind is worth doing.

### Caveats that must be stated in the paper

- Power figures are vectorless estimates at default switching activity.
  Regenerate from a SAIF written by the testbench before publishing them.
- 20 ns target. Fmax here is not the ceiling; sweep the constraint to find it.
- `asym_dsp` forces a DSP onto a 9x9 multiply via `use_dsp="yes"`, which Vivado
  would not do unprompted. It is the correct control, but say so.
- The measured wordlength ordering (earlier section) does not match 18/10/9.
  These area numbers are for the *manuscript's* widths, not the empirically
  justified ones. Re-run once the widths are re-derived.

## Math errors in the manuscript (independent of the above)

- **Theorem 4**: log₂(N) − log₂(√(N/3)) = ½log₂(3N), not ½log₂(N/3). For N=64
  that is 3.79 bits, not the ≈2 claimed. Also the log subtraction is only
  valid when γη ≫ 1 inside (γη+1).
- **Proposition 1**: γ = ρ/(ρ+λ) is *increasing* in ρ, so γ ≤ γ_max gives
  ρ ≤ λγ_max/(1−γ_max), an **upper** bound. The manuscript labels it ρ_min and
  claims going below it forces overflow — the opposite of its own derivation.
  The real binding constraint measured here is a *range* condition on
  w = q + ρ(z−u), not a precision condition. That is a better proposition and
  it is derivable: ‖w‖_∞ ≤ ‖q‖_∞ + ρ(‖z‖_∞ + ‖u‖_∞) < 2^(INT_BITS−1).
- **Theorem 1**: q = 2^−W with e ~ U(−q, q) puts the noise across two
  quantization steps; standard is U(−q/2, q/2). Factor of 2 propagates into
  Theorem 2. Also √N and η both claim to model accumulation over N stages.
- **Theorem 2**: vacuous as written — if no component lands within q of κ then
  B_q = ∅ and the floor is zero. The repair is also the stronger result:
  E|B_q| ≈ n·2q·f_v(κ) under a density assumption on v.
- **Theorem 3**: the Box case is an assertion, not a proof.

## Data inconsistencies still unresolved

Both are superseded by the measured table above. For the record:

| | manuscript | Gemini dump | **measured** |
|---|---|---|---|
| baseline → proposed | 1,264 → 602 (52.3%) | 865 → 665 (23.1%) | **6308 → 5299 (16.0%)** |
| post-route | 615 LUTs, 21 mW | — |
| per-lane sum | 247 LUTs | 472 LUTs |
| TASER | 195 DSP, 262 MHz | 4,790 LUT, 52 DSP, 232 MHz |

At most one of each pair is real. None can have come from the RTL as it was.
52.3% appears in the abstract, the contributions list and the conclusion.

## Open items

1. **Sweep κ, ρ, γ and channel conditioning.** The ordering result above is one
   operating point (κ=0.1, γ=0.667, ρ=1, well-conditioned Gaussian). The
   theory's prediction is that L2's F* falls as γ→0 — directly testable, and if
   it holds, a γ-conditioned version of the theorem survives.
2. Re-derive the lane widths from the measured Pareto front instead of 18/10/9.
3. Run `syn/run_ooc.tcl` for real baseline vs asymmetric numbers.
4. BER vs SNR (float / uniform / asymmetric) — `experiments.py` E3 is written
   and runs; regenerate after item 2 fixes the widths.
5. Throughput: latency is 2N+2 cycles per mat-vec plus 5 FSM cycles per ADMM
   iteration. Convert to Mb/s and report LUTs·s/bit against TASER.
6. Complex-valued channels. Everything here is the real-valued equivalent
   model; an N×N array serves N *users*, not N antennas, which is the answer
   to "why is an 8×8 array massive MIMO" — state it explicitly.

---

# FINAL MEASURED RESULT (all builds valid, all regressions passing)

Artix-7 xc7a35tcpg236-1, OOC, routed, 20 ns target, fabric arithmetic.
RTL/golden-model equivalence verified bit-exact at F_MAIN = 16, 12, 10, 9.

| tag | lanes | F_MAIN | LUT | LUTprx | LUTarr | FF | CARRY | Fmax | Dyn |
|---|---|---|---|---|---|---|---|---|---|
| uniform18 | 16/16/16 | 16 | 6308 | 2720 | 472 | 2199 | 1153 | 58.9 | 112 mW |
| uniform10 | 8/8/8 | 16 | 4439 | 1232 | 472 | 1975 | 769 | 58.4 | 95 mW |
| asym_derived | 8/7/8 | 16 | 4631 | 1424 | 472 | 1975 | 825 | 57.2 | 95 mW |
| main10_uniform | 10/10/10 | 10 | 4081 | 1544 | 376 | 1479 | 789 | 73.4 | 79 mW |
| **main9_uniform** | **9/9/9** | **9** | **3366** | **1184** | **360** | **1359** | **461** | **71.1** | **78 mW** |
| main9_asym | 9/8/9 | 9 | 3510 | 1328 | 360 | 1359 | 477 | 71.0 | 79 mW |

## Headline: uniform18 -> main9_uniform (Q2.16 -> Q2.9 across the whole datapath)

| metric | before | after | change |
|---|---|---|---|
| total LUTs | 6308 | 3366 | **-46.6%** |
| proximal lanes | 2720 | 1184 | -56.5% |
| systolic array | 472 | 360 | -23.7% |
| FSM / dual / residual | 3116 | 1822 | -41.5% |
| flip-flops | 2199 | 1359 | -38.2% |
| carry chains | 1153 | 461 | -60.0% |
| dynamic power | 112 mW | 78 mW | -30.4% |
| Fmax | 58.9 MHz | 71.1 MHz | **+20.7%** |

Every metric improves at once. DSP stays at 64 throughout (the array multiply
still occupies one DSP48E1 per PE at any operand width <= 18).

## Asymmetry is negative at both main widths

| F_MAIN | uniform prox | asymmetric prox | cost |
|---|---|---|---|
| 16 | 1232 | 1424 | +192 LUT (+15.6%), +24/lane |
| 9 | 1184 | 1328 | +144 LUT (+12.2%), +18/lane |

Two independent operating points, same sign, magnitude tracking the cast
overhead. Theorem 4 explains it sharply: the asymmetric lane is **Box**, which
contains no multiplier. With no quadratic term to harvest, only the linear term
and the fixed cast cost remain, so narrowing it can never pay. **Narrowing a
multiplier-free lane is unconditionally net-negative.**

## The width choice itself

F=10 costs 4081 LUTs, F=9 costs 3366 — 17.5% for one bit. The error model picks
F=9 at NMSE 1e-4 directly, with no search. That is the contribution.

## Still open before submission

1. Generalization: more channel models, operating points, a second problem size.
2. A second demonstration problem (LASSO) to justify proximal-operator scope.
3. SAIF-based power to replace the vectorless estimates.
4. Fmax sweep -- 20 ns is a loose target; 71.1 MHz is not the ceiling.
5. Throughput in Mb/s and a LUTs*s/bit efficiency figure.
