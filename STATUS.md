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
| ~~dynamic power~~ | ~~112 mW~~ | ~~91 mW~~ | ~~18.8%~~ **REFUTED** |
| dynamic power (MEASURED, SAIF) | 11 mW | 11 mW | **none** |
| Fmax | 58.9 MHz | 59.6 MHz | no penalty (both extrapolated) |

**The 18.8% power reduction does not exist.** (2026-09-04) SAIF measurement of
`uniform_nodsp` and `asym_nodsp` gives 11 mW dynamic for BOTH, 68 mW static for
both, 80 vs 79 mW total — inside the 1 mW report rounding. The 112/91 pair was
two vectorless estimates, ~10x high, and their difference was an artefact of
the estimator rather than of the design.

Both runs Confidence High (75% / 72% nets matched) and bit-exact against the
golden model. Repeatability check: `uniform_nodsp` is the same configuration as
`uniform18`, and two independent SAIF captures returned identical dynamic power.

This strengthens the negative result rather than weakening it. Asymmetry costs
area at both main widths AND buys no power. One consistent finding.

Caveat to state: the two builds ran different vector sets (`_unif` vs `_asym`)
and converged differently (box: 32 vs 23 iterations, again quantisation
stagnation, not faster convergence). The asymmetric build therefore ran a
SHORTER workload and still showed no power advantage, so the confound does not
threaten a null result — but it would threaten a positive one.

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

- Power figures IN THIS SECTION are still vectorless estimates at default
  switching activity. Only uniform18 and main9_uniform have been re-measured
  from SAIF (see FINAL MEASURED RESULT). The 112/91/95/94 mW figures in the
  tables above are ~10x overestimates and must not be published as-is.
  The 18.8% asymmetric power reduction (Result 1) rests on two vectorless
  numbers and is UNVERIFIED -- re-measure or drop it.
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

**The `Dyn` column above is VECTORLESS and ~10x too high.** Measured values
exist only for uniform18 (11 mW) and main9_uniform (7 mW). The `Fmax` column
is 1000/(20 ns - slack), i.e. an extrapolation from a loose 20 ns constraint,
not a period the build was shown to meet. Neither column may be quoted until
replaced -- see the SAIF section below and the pending Fmax sweep.

## Headline: uniform18 -> main9_uniform (Q2.16 -> Q2.9 across the whole datapath)

| metric | before | after | change |
|---|---|---|---|
| total LUTs | 6308 | 3366 | **-46.6%** |
| proximal lanes | 2720 | 1184 | -56.5% |
| systolic array | 472 | 360 | -23.7% |
| FSM / dual / residual | 3116 | 1822 | -41.5% |
| flip-flops | 2199 | 1359 | -38.2% |
| carry chains | 1153 | 461 | -60.0% |
| dynamic power (MEASURED, SAIF) | 11 mW | 7 mW | ~-36% (see below) |
| ~~dynamic power (vectorless)~~ | ~~112 mW~~ | ~~78 mW~~ | ~~-30.4%~~ WITHDRAWN |
| Fmax (MEASURED, swept) | 66.3 MHz | 85.4 MHz | **+28.8%** |
| ~~Fmax (extrapolated)~~ | ~~58.9 MHz~~ | ~~71.1 MHz~~ | ~~+20.7%~~ SUPERSEDED |
| throughput @ fixed iters | 79.4 k solves/s | 102.3 k solves/s | **+28.8%** |
| energy per solve | 184 nJ | 117 nJ | **-36%** |

Every metric improves at once. DSP stays at 64 throughout (the array multiply
still occupies one DSP48E1 per PE at any operand width <= 18).

### Power: vectorless figures withdrawn, replaced by SAIF measurement (2026-09-04)

The 112/78 mW pair was vectorless -- Vivado's default-toggle-rate estimate, not
a measurement. Post-route gate-level simulation writing a SAIF, then
`report_power` consuming it, gives:

| build | dynamic | device static | total on-chip | confidence | nets matched |
|---|---|---|---|---|---|
| uniform18 | 11 mW | 68 mW | 80 mW | High | 74% (12246/16519) |
| main9_uniform | 7 mW | 68 mW | 76 mW | High | 72% (6347/8763) |

Both builds measured through the identical flow, both bit-exact against the
golden model in the same run that produced the activity.

Three things follow, and all three must reach the paper:

1. **The vectorless numbers were ~10x too high.** 112 -> 11 mW, 78 -> 7 mW.
   The RATIO survived roughly intact by luck, not by construction.
2. **This design is static-dominated.** Static is 68 mW of the 76-80 mW total
   and is a device property, identical across builds. Total on-chip power
   therefore falls only 5.0% (80 -> 76 mW). Any claim about "power" must say
   DYNAMIC explicitly or it is wrong by a factor of seven.
3. **The reduction is ~36%, not 30.4%** -- but the reports round to 1 mW, so
   7 and 11 carry +-0.5 mW and the honest bound is 29-44%. Quote the ABSOLUTE
   values (11 mW -> 7 mW); a percentage from single-digit mW readings implies
   precision that does not exist. Energy per solve (cycles x period x dynamic)
   is the better metric and uses the exact integer cycle counts below.

Dynamic breakdown, mW: clocks 5 -> 3, signals 2 -> <1, slice logic 1 -> <1,
DSP 3 -> 2. Clock power dominates in both; fewer flops at Q2.9 means fewer
clock loads.

Near-miss worth recording: comparing the vectorless uniform18 (112 mW) against
a measured main9 (7 mW) would have produced a fabricated 94% reduction. The
only thing that caught it was an object-count guard printing zero.

### Fmax (MEASURED by constraint sweep, 2026-09-04)

`syn/fmax_sweep.tcl`, binary search on the clock constraint, 7 steps per build,
full synth+place+route at each step. Fmax = 1000/(tightest period that actually
MET timing) -- never 1000/(period - slack).

| build | period met | Fmax | WNS | LUT at that period |
|---|---|---|---|---|
| uniform18 | 15.079 ns | 66.3 MHz | +0.079 ns | 6308 |
| main9_uniform | 11.703 ns | 85.4 MHz | +0.096 ns | 3366 |

**+28.8%**, superseding the +20.7% figure, which came from 1000/(20 ns - slack)
at a deliberately loose constraint and understated both builds.

Search bracket (last MISS to last MET): uniform18 14.938 -> 15.079 ns,
main9 11.562 -> 11.703 ns. True Fmax lies in 66.3-67.0 and 85.4-86.5 MHz, so
the ratio is bounded **+27.6% to +30.4%**.

**CORRECTION (2026-09-20, supersedes the 09-04 correction below): the
4673-vs-6308 gap is the COUNTING METHOD, not the timing constraint.**
`harvest.tcl` and `fmax_sweep.tcl` count LUT *cells*
(`get_cells REF_NAME =~ LUT*`); after LUT combining two cells share one
physical LUT6, so the cell count runs high. `report_utilization` gives the
Slice LUTs every other paper quotes. For uniform18 both are from the SAME
20 ns checkpoint: 6308 cells, 4673 Slice LUTs. The fmax sweep log prints
LUT=6308 at EVERY period it tried, met or missed, which is the proof that the
constraint is not what moves it. Ratios: -46.6% by cells, -44.9% by Slice
LUTs; the headline survives either way. Use `tools/util_table.py` (Slice LUTs)
for anything compared against other work -- COMPARISON.md does. The earlier
"+35% from timing-driven replication" reading was wrong. Area and speed therefore come from the same design points and
-46.6% / +28.8% may be quoted together. (One artefact worth knowing: uniform18
synthesised to 6420 LUTs at an infeasible 11.0 ns, timing-driven replication
under a constraint it could not meet. It does not enter any result.)

### All six builds swept and measured (2026-09-04)

| build | F_MAIN | lanes | LUT | Fmax (MHz) | period met (ns) |
|---|---|---|---|---|---|
| uniform18 | 16 | 16/16/16 | 6308 | 66.3 | 15.079 |
| uniform10 | 16 | 8/8/8 | 4439 | 67.6 | 14.797 |
| asym_derived | 16 | 8/7/8 | 4631 | 63.9 | 15.640 |
| main10_uniform | 10 | 10/10/10 | 4081 | 79.7 | 12.547 |
| **main9_uniform** | **9** | **9/9/9** | **3366** | **85.4** | **11.703** |
| main9_asym | 9 | 9/8/9 | 3510 | 86.5 | 11.562 |

Reproducibility: uniform18 and main9_uniform were swept twice (separate runs,
`fmax_sweep.log` and `fmax_all.log`) and returned identical periods.

#### The asymmetry penalty is +4.3% LUT at BOTH widths

Matched pairs — same F_MAIN, one lane narrowed, nothing else changed:

| pair | LUT | Fmax |
|---|---|---|
| asym_derived vs uniform10 (F_MAIN=16) | **+4.3%** | -5.5% |
| main9_asym vs main9_uniform (F_MAIN=9) | **+4.3%** | +1.3% |

Identical to one decimal place at two different widths. This is now a
reproducible cost, not a coincidence of two similar numbers.

The Fmax effect is INCONSISTENT IN SIGN and must not be claimed either way:
the +1.3% is one binary-search step (main9_asym met at 11.562 ns, exactly the
period main9_uniform missed), i.e. at the resolution limit of the sweep.

Power, measured: main9_asym is 7 mW dynamic / 68 mW static / 76 mW total,
Confidence High, 73% nets matched — IDENTICAL to main9_uniform. Third
independent null on asymmetry power (after uniform_nodsp vs asym_nodsp).

**Statement for the paper: per-operator asymmetry costs 4.3% area at both
main-datapath widths, buys no measurable dynamic power, and has no consistent
frequency effect.** Measured, not estimated, on both axes.

### Board validation (2026-09-17)

uniform18 and main9_uniform, all three operators, **bit-exact on a physical
Basys3**, verified by `tools/board_capture.py` over UART. Details and the four
bring-up bugs in BOARD.md. Wall power not yet measured (instrumentation).

#### MECHANISM FOUND: two critical-path regimes (2026-09-04)

Worst-path endpoints from `*_timing_route.rpt` split the seven builds into
exactly two families, and family membership predicts the Fmax band perfectly.

**Family A -- prox lane path** (`v_reg` -> `G_PROX[i].u_prox/z_out_reg`,
21-25 logic levels, 13-15 CARRY4):

| build | delay @20ns | Fmax |
|---|---|---|
| uniform18 (F16, L16) | 16.924 | 66.3 |
| uniform10 (F16, L8) | 17.115 | 67.6 |
| asym_derived (F16, L8/7/8) | 17.472 | 63.9 |
| main10_lane8 (F10, L8) | 16.110 | 68.9 |

**Family B -- residual/convergence path** (`r_abs_reg` -> `converged_reg`,
17 logic levels, 8 CARRY4):

| build | delay @20ns | Fmax |
|---|---|---|
| main10_uniform (F10, L10) | 13.568 | 79.7 |
| main9_uniform (F9, L9) | 14.006 | 85.4 |
| main9_asym (F9, L9/8/9) | 14.087 | 86.5 |

**Perfect separation: A spans 63.9-68.9 MHz, B spans 79.7-86.5. No overlap.**

**Mechanism.** Fmax = 1/max(prox path, residual path). Narrowing a lane below
F_MAIN inserts a q_narrow cast into the prox path; when that lifts the prox
path above the residual path, the build drops into the slow regime.

- `main10_lane8`: lanes 8 at F_MAIN=10 -> cast -> prox binds -> 68.9, eleven
  MHz below its lane-uniform sibling despite the same main datapath.
- `main10_uniform`: lanes == F_MAIN -> no cast -> residual binds -> 79.7.
- `uniform18`: prox-bound WITHOUT casts, because at W=18 the prox datapath is
  wide on its own (25 levels, 15 CARRY4). This is why lane width barely moves
  Fmax at F_MAIN=16 -- the prox path binds either way.
- `main9_asym`: a 1-bit Box cast is not enough to lift the prox path above the
  residual path at F=9, so it stays in the fast regime -- which is exactly why
  it shows no Fmax penalty.

Within-family spread is ~8% both times (63.9-68.9, 79.7-86.5) and is
implementation noise. The between-family gap is structural.

**Claim for the paper:** Fmax is set by WHICH path binds, not by F_MAIN
directly. Narrowing the main datapath raises Fmax only while the residual
path binds; once a narrowing cast pushes the prox path above it, further
narrowing buys nothing. The headline comparison (uniform18 -> main9_uniform)
crosses regimes, which is why it shows +28.8%.

CAVEAT: these are 20 ns reports, where the tool stops optimising once timing
is met, so the delays are "good enough" not "best possible". `syn/critpath.tcl`
re-runs each build at its OWN Fmax to confirm the family split persists.
Predictions registered before that run: (1) the A/B split holds at Fmax;
(2) main10_lane8 stays prox-bound -- if it flips, the mechanism is wrong.

**CONFIRMED at each build's own Fmax (`critpath.log`, 2026-09-04).** Logic
levels are cleanly bimodal with nothing in between:

| build | levels @ own Fmax | levels @ 20 ns | family |
|---|---|---|---|
| uniform18 | 24 | 25 | A (prox) |
| uniform10 | 22 | 21 | A |
| asym_derived | 22 | 23 | A |
| main10_lane8 | **21** | 21 | A |
| main10_uniform | 17 | 17 | B (residual) |
| main9_uniform | 17 | 17 | B |
| main9_asym | 16 | 17 | B |

Both predictions hold. main10_lane8 stays prox-bound (21 levels) while
main10_uniform at the SAME F_MAIN sits at 17. All slacks 0.020-0.148 ns, so
these are genuine Fmax points. The 20 ns split was not a relaxed-constraint
artifact. **Endpoints confirmed from `*_critpath.rpt` -- module identity measured, not
inferred:**

| build | worst path @ own Fmax | levels | family |
|---|---|---|---|
| uniform18 | `v_reg[40]` -> `G_PROX[2].u_prox/z_out_reg[11]` | 24 | A |
| uniform10 | `v_reg[138]` -> `G_PROX[7].u_prox/z_out_reg[10]` | 22 | A |
| asym_derived | `v_reg[98]` -> `G_PROX[5].u_prox/z_out_reg[12]` | 22 | A |
| main10_lane8 | `v_reg[14]` -> `G_PROX[1].u_prox/z_out_reg[5]` | 21 | A |
| main10_uniform | `s_abs_reg[86]` -> `converged_reg` | 17 | B |
| main9_uniform | `r_abs_reg[79]` -> `converged_reg` | 17 | B |
| main9_asym | `s_abs_reg[80]` -> `converged_reg` | 16 | B |

Every Family A path terminates in a proximal lane's `z_out` register; every
Family B path terminates at `converged_reg`. No build is ambiguous and the
families never share an endpoint.

**The decisive pair is main10_lane8 vs main10_uniform**: same F_MAIN=10, same
main datapath, differing only in lane width, and they bind on DIFFERENT paths.
The mechanism is isolated to one variable.

Wording note: Family B alternates between `r_abs_reg` (primal residual) and
`s_abs_reg` (dual residual) across builds. Both feed `converged_reg` through
the same comparison logic, so this is the CONVERGENCE-TEST path, not "the
primal residual path". Do not name a specific residual in the paper.

#### SCOPED EARLIER (superseded by the mechanism above)

`main10_lane8` (F_MAIN=10, lanes 8/8/8) was added as the single-variable
control. Measured: **68.9 MHz, 3665 LUT (own Fmax), 7 mW dynamic.**

Predicted before the run: ~79-80 MHz if F_MAIN controls frequency. **The
prediction FAILED.** Single-variable comparisons at own Fmax:

| isolated variable | LUT | Fmax |
|---|---|---|
| F_MAIN 16 -> 10, lanes fixed at 8 | -17.4% | 67.6 -> 68.9 (**+1.9%**) |
| lanes 8 -> 10, F_MAIN fixed at 10 | +11.4% | 68.9 -> 79.7 (**+15.7%**) |

Narrowing the main datapath buys almost NO frequency once lanes are held
fixed, and WIDENING lanes to match F_MAIN makes the design faster. The
obvious mechanism (lane != F_MAIN forces a narrowing cast, i.e. rounding
logic with a carry chain) does not survive either: `uniform10` (F=16, lanes 8,
casts present) is FASTER than `uniform18` (F=16, lanes 16, no casts),
67.6 vs 66.3 MHz.

**What survives.** Among builds where lanes == F_MAIN, Fmax is monotone in
F_MAIN: 66.3 (16) -> 79.7 (10) -> 85.4 (9). Narrowed-lane builds do not follow
this curve. The HEADLINE IS UNAFFECTED -- uniform18 and main9_uniform both
have lanes == F_MAIN, so +28.8% is a clean within-regime comparison.

**DO NOT CLAIM** "narrowing the main datapath raises Fmax" in general. Scope
it to uniform-lane configurations or drop it.

**Area is the robust axis.** F_MAIN 16->10 gives -17.4% and lanes 10->8 gives
-10.2% at own Fmax, matching the 20 ns numbers (-17.2%, -11.3%). Both axes
are real; per bit, LANES are the more efficient axis (-5.1%/bit vs -2.9%/bit)
-- the reverse of what the confounded comparison suggested.

**Power.** main10_lane8 is 7 mW dynamic, identical to main10_uniform and
main9_uniform. Narrowing lanes buys no power at any F_MAIN tested.

#### SUPERSEDED: original claim (confounded, retained for the record)

Two ways to narrow, both starting from uniform18 (6308 LUT, 66.3 MHz):

| change | LUT | Fmax |
|---|---|---|
| lanes only, 16 -> 8 (uniform10, F_MAIN stays 16) | -29.6% | **+2.0%** |
| main datapath -> 10, lanes 10 (main10_uniform) | -35.3% | **+20.2%** |
| main datapath -> 9, lanes 9 (main9_uniform) | -46.6% | **+28.8%** |

`main10_uniform` beats `uniform10` on BOTH area and frequency despite having
WIDER lanes (10 vs 8). Narrowing the main datapath strictly dominates
narrowing the lanes.

**Halving all three lanes buys 2.0% frequency.** The critical path runs
through the main datapath (array and accumulator), not the proximal lanes, so
lane width cannot touch it.

This also EXPLAINS the negative result: narrowing a lane removes logic that
was never on the critical path, while adding the width-mismatch casts that
cost the 4.3%. Prior confirmation of the same effect exists in Wu et al. 2022
Table 1 (their ADMM FXP20->24 uses 6807 LUT vs consistent FXP24's 6775) —
see RELATED_WORK.md.

#### F_MAIN dominance confirmed on DYNAMIC POWER too (all six builds measured)

| build | F_MAIN | lanes | dynamic | total | confidence | nets matched |
|---|---|---|---|---|---|---|
| uniform18 | 16 | 16/16/16 | 11 mW | 80 mW | High | 74% |
| uniform10 | 16 | 8/8/8 | 10 mW | 78 mW | High | 75% |
| asym_derived | 16 | 8/7/8 | 11 mW | 79 mW | High | 72% |
| main10_uniform | 10 | 10/10/10 | 7 mW | 76 mW | High | 73% |
| main9_uniform | 9 | 9/9/9 | 7 mW | 76 mW | High | 72% |
| main9_asym | 9 | 9/8/9 | 7 mW | 76 mW | High | 73% |

Halving all three lanes saves 1 mW. Narrowing the main datapath saves 4 mW.
`main10_uniform` beats `uniform10` on dynamic power as well as area and
frequency, despite having WIDER lanes.

**The mechanism, in the clock-power column:**

| | uniform18 | uniform10 | main10 | main9 |
|---|---|---|---|---|
| clocks | 5 mW | **5 mW** | 4 mW | 3 mW |

Clock power is FLAT under lane narrowing and monotone in F_MAIN. Lane width
does not reduce flop count in the main datapath, so it touches neither the
clock tree nor the critical path. That is why lanes buy 2.0% Fmax and 9%
dynamic power while F_MAIN buys 20% and 36%.

#### Complete measured picture, all changes relative to uniform18

| change | LUT | Fmax | dynamic power | energy/solve (K=32) |
|---|---|---|---|---|
| lanes only, 16 -> 8 | -29.6% | +2.0% | -9% | 184 -> 167 nJ |
| main datapath -> 10, lanes 10 | -35.3% | +20.2% | -36% | 184 -> 117 nJ |
| main datapath -> 9, lanes 9 | -46.6% | +28.8% | -36% | 184 -> 117 nJ |

**Limit to state honestly: dynamic power SATURATES at F_MAIN=10.** main10 and
main9 both read 7 mW, indistinguishable at the report's 1 mW resolution, while
LUT keeps falling (4081 -> 3366) and Fmax keeps rising (79.7 -> 85.4). The
last bit of narrowing buys area and speed but no further measurable power.

Caveat carried forward: `uniform10`'s l1 case hit MAX_ITER=32 (truncated, not
converged), as did `uniform18`'s box case. Does not affect the power
comparison, but belongs with the iteration-count caveat.

#### Throughput law confirmed on a fourth build

main9_asym: 393/471/315 at 15/18/12; uniform10: 835/601/523 at 32/23/20;
main10_uniform: 471/575/367 at 18/22/14. All exactly 26K+3. The law now holds
across ALL SIX BUILDS -- four main-datapath widths, symmetric and asymmetric.
Cycles per iteration are invariant to every width parameter, so every
performance claim rests on Fmax alone.

### Derived performance (2026-09-04)

Throughput at FIXED iteration count K, cycles = 26K+3 identical across builds:

| K | cycles | uniform18 | main9_uniform | speedup |
|---|---|---|---|---|
| 20 | 523 | 126.8 k solves/s | 163.4 k solves/s | +28.8% |
| 32 | 835 | 79.4 k solves/s | 102.3 k solves/s | +28.8% |

Speedup equals the Fmax ratio exactly, because cycles per iteration are
identical. Narrowing buys frequency, not cycles.

**Energy per solve: 184 nJ -> 117 nJ, -36%** (K=32). Dynamic energy per cycle
is CV^2 and so frequency-independent, which means this figure does NOT depend
on which operating frequency is chosen -- a cleaner claim than power, which
does. The 1 mW report rounding bounds it at -29% to -43%.

This is the number to lead with. It combines the width reduction, the measured
activity and the measured cycle count in one quantity, and it is invariant to
the clock the reviewer imagines running at.

### Throughput (MEASURED, post-route gate-level, 2026-09-04)

| build | l1 | box | l2 |
|---|---|---|---|
| uniform18 | 28 iters / 731 cyc | 32 iters / 835 cyc | 22 iters / 575 cyc |
| main9_uniform | 15 iters / 393 cyc | 19 iters / 497 cyc | 12 iters / 315 cyc |

**cycles = 26 x iterations + 3**, fitting all six cases exactly, IDENTICAL
across both builds. Narrowing buys nothing per iteration; every speed claim
therefore rests entirely on Fmax.

Two traps in this table:

- **Iteration counts are not comparable.** main9 needs fewer iterations only
  because `eps=0` makes the early exit fire when the residual quantises to
  exactly zero -- stagnation, not convergence. Computing solutions/s per build
  from its own iteration count bakes in a fake ~1.8x. Hold iterations fixed.
- `box_unif` at uniform18 hit 32 = MAX_ITER, so that case was truncated, not
  solved.

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
2. ~~A second demonstration problem (LASSO)~~ DONE 2026-09-20. T1 0.98–1.03
   at native d ≤ 0.77; F* 8 (m=32) to 10–11 (m=6); support ≥99% prediction
   FAILED (90–100%, mismatches ≤2 LSB, post-hoc); RTL bit-exact at F=16 and 9.
   Full table in THEOREM_LOCK.md, "SECOND PROBLEM: LASSO".
3. ~~SAIF-based power~~ DONE 2026-09-04 for uniform18 and main9_uniform.
   Still vectorless for the other four builds and for the asymmetry study.
4. ~~Fmax sweep~~ DONE 2026-09-04: 66.3 / 85.4 MHz, +28.8%. Other four
   builds still carry extrapolated Fmax and must not be quoted.
5. ~~Throughput~~ DONE: 26 cycles/iteration + 3, both builds; solves/s and
   energy per solve derived above. A LUTs*s/bit efficiency figure still needs
   a defined payload size.
