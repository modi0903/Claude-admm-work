# HANDOFF — read this first

Entry point for a fresh conversation. Upload this file plus the repo; it
replaces the entire chat history.

## What this project is

A fixed-point wordlength study for ADMM hardware accelerators. Two analytic
models — one for error, one for fabric cost — validated against a bit-exact
software model and routed Artix-7 silicon.

Target: **FCCM 2027**, deadline ~mid-Jan 2027. Backups: FPL 2027 (~Mar),
IEEE TVLSI / TCAS-I (rolling). IEEE venues preferred (college sponsors them).

## The one rule

**No number enters the manuscript unless a script in this repo produces it.**
Every model claim gets a falsifier written and run *before* the claim is
drafted. Two of the main results are negative; this discipline is why they are
credible.

## Repo map

```
rtl/     admm_defs.vh q_cast.v sat_shift.v max_tree.v pe_mac.v
         systolic_array.v reconfigurable_prox.v admm_top.v
tb/      tb_admm_top.v + vectors/
model/   fxp_admm.py          bit-exact model, mirrors each RTL primitive
         gen_vectors.py       golden vectors at F_MAIN=16
         gen_vectors_fm.py    golden vectors at any F_MAIN
         experiments.py       wordlength / convergence / BER
         error_decomp.py      Theorem 1 falsifier
         annihilation.py      the (1-d) mechanism test
         lattice_rule.py      lattice design rule
         metric_check.py      NMSE vs absolute metric
         derive_widths.py     lane width derivation
         main_sweep.py        main-datapath sweep
         generalize.py        Sprint 1 generalisation
         loop_gain.py         Sprint 1b loop-gain model
         margin.py            held-out test of the loop-gain fit
         lasso.py             second problem (P-L1..P-L3; --e3 post-hoc)
         gen_vectors_lasso.py LASSO golden vectors (P-L4), any F_MAIN
tools/   util_table.py        routed Slice LUT/FF/DSP (the metric others quote)
         comparison_table.py  COMPARISON.md and the paper's table
syn/     run_ooc.tcl  harvest.tcl
```

Docs, in reading order: **TODO.md** (what to do next) → **STATUS.md** (all
measured results) → **THEORY_PLAN.md** (proofs, appendices A–D) →
**SPRINT1_RESULT.md** (latest experiments) → **RELATED_WORK.md** (novelty
position) → **COMPARISON.md** (prior accelerators, with provenance). SPRINT.md is superseded by TODO.md; keep it only for the venue
research.

## Verify in two minutes

```
build.bat 1          # Windows; or iverilog with files named explicitly
build.bat 0
build.bat 0 lasso    # second problem, same RTL
```
Both must print `PASS: all lanes bit-exact vs golden model`.
Regression also passes at F_MAIN = 16, 12, 10, 9.

## Established results

**Error model (validated).** A proximal operator's precision requirement
follows from its *degenerate set* — the region where output does not depend on
input, where a perturbation is annihilated exactly. Effective noise scales with
(1−d), not the classical flat q²/12. Model/measured = 0.99 (L1), 1.00 (Box)
over d ∈ [0.12, 0.88]. Classical model wrong by 3–4× on average, 900× at
d = 0.999. At d = 1 measured error is exactly zero.

**Lattice rule (validated).** An operator constant not representable on its
lane's lattice costs exactly one bit. Measured 3.68–3.90× error penalty against
a predicted 4×; one bit through the closed loop, metric-independent.

**Cost model (silicon) — LINEAR at lane granularity.** Lane area is
A(W) = b·W + c, b ≈ 19.6 LUT/bit, validated out-of-sample (predicts lane 8 at
−6.3%). The quadratic form was REJECTED by its held-out test (−21.6%, fitted
a < 0). The W² law (166 vs 35 LUTs, ratio 4.74) holds only for the isolated
gamma multiplier. Cast cost measured directly: ~0.9 LUT/bit/lane.

**Main result (silicon, all MEASURED).** uniform18 → main9_uniform (Q2.16 →
Q2.9): LUT −46.6%, Fmax 66.3 → 85.4 MHz (+28.8%, swept), dynamic power
11 → 7 mW (SAIF, Confidence High), energy/solve 184 → 117 nJ. Quote DYNAMIC
power: static is 68 mW of ~76–80 total, so total falls only 5%. The old
"power −30.4% / Fmax +20.7%" figures were vectorless / extrapolated and are
WITHDRAWN. Cycles = 26·iters + 3 in every build.

**Board (silicon, 2026-09-17).** Basys3, both uniform18 and main9_uniform, all
three operators bit-exact vs golden over UART (`tools/board_capture.py`). Chain
is complete: model → golden → post-route gate-level → hardware. See BOARD.md.

**Negative result (silicon).** Per-operator asymmetry costs +4.3% LUT at BOTH
F_MAIN=16 and 9, with identical dynamic power (three measured null pairs) and
no consistent Fmax effect. Wu et al. 2022 Table 1 corroborates independently.

**Fmax mechanism.** Two critical-path regimes: prox-lane path (21–24 levels,
63.9–68.9 MHz) vs convergence-test path (16–17 levels, 79.7–86.5 MHz). A lane
narrower than F_MAIN inserts a cast that pushes the prox path into the slow
regime. main10_lane8 vs main10_uniform isolates it. See STATUS.md.

**Loop gain — generalises for L2 ONLY (held-out test, 2026-09-20).** Fitted on
seeds 7000+, tested on disjoint seeds (`model/margin.py`): L2 0.046 bits held
out (1 bit of margin covers 99% of instances); L1 1.38 and Box 0.73 bits held
out. The L1/Box fits (d, d²) and P0.1 are RETRACTED. For L1 one instance is 68%
of the ensemble MSE and the ensemble moves 0.59 bits between seed sets. The old
LOO figures (0.340/0.234/0.031) were on the same seeds and could not see this.
Any bit figure must say in-sample / LOO / held-out. What survives for L1/Box
is the zero-parameter T2 gap predictor. No mechanism is claimed.

**Second problem: LASSO (2026-09-20).** Same RTL, unchanged. T1 holds at
0.981–1.028 on LASSO's native distribution (d 0.62–0.77, κ off-lattice) —
the first L1 validation at native high d. F* tracks ‖M‖₂: 8 at m=32, 9 at
m=16, 9–11 at m≤8. Support-fidelity prediction (≥99%) FAILED at 90–100%;
post-hoc, every mismatch is ≤2 LSB. RTL bit-exact at F=16 and 9
(`build.bat 0 lasso`). Table in THEOREM_LOCK.

**Contraction lives at the loop, not the operator.** Resolvent saturates at
3.18 with g = 0.667 vs divergence at g = 1. Composition (old Theorem 5) failed
at 2.509 bits and is demoted.

## Claim set — see THEOREM_LOCK.md (authoritative)

Claimed: T1 degenerate-set (1−d) annihilation (0.99 L1, 1.00 Box; L2 0.88 —
say so); Prop 1 ρ bound (pre-registered); T4 asymmetry net-negative; linear
lane-area law; measured hardware characterisation of 7 builds.
Restated: T2 ordering -- crossover confirmed; mechanism is operator coefficient
x loop resolvent (zero fitted parameters), NOT the operator alone (see
THEOREM_LOCK). Demoted: T5 composition.

**Do not claim:** "first error model for fixed-point ADMM" (Jerez et al.,
arXiv:1303.1090, have one); "analytic instead of search"; the DSP operand-width
threshold; any mechanism for the L1/Box sign difference; per-instance validity
of the loop-gain model; total-power reduction without saying "dynamic".

**Positioning:** Jerez et al. identify the diagonal [0,1] scaling at the
projection and DISCARD it; Kinsman & Nicolici (TCAD 2011) say correlation "can
be captured into constraints" if known; Ha & Sentieys (DATE 2020/2023) say
analytical models remain limited to LTI. (1−d) is that characterisation. See
RELATED_WORK.md, which also records the literature pass (P4 discharged).

## Open work — see TODO.md

Board bring-up DONE. Done 2026-09-20: T2 restated, held-out test of loop gain (L1/Box retracted),
per-instance margin (L2: +1 bit), 0.5-bit criterion justified, kappa term and
outlier explanation refuted (L1-Box residual open). LASSO done (P-L3 failed, stated).
Comparison table done
(COMPARISON.md; T must vet fairness and verify the AccelMPC row).
Remaining: wall power (blocked on a bench supply / meter
with ≤1 mA resolution; the build-to-build delta is ~4 mW), optional LASSO
board run at F=9 (BOARD.md). Then draft from
`paper/admm_wordlength.tex` (internal record, not a submission).

## Working context

Supervisor is on maternity leave and largely unavailable. Work is self-directed;
she remains a co-author and will need to sign off. Send a short written update
every two weeks that requires no reply.

## Traps already hit — do not repeat

- Part-selects of a localparam are **unsigned** in Verilog. Every comparison
  against a lane constant needs `$signed()`.
- Bit-slicing a constant to narrow it gives garbage (gamma 16384 → 9 bits = 0).
  Re-derive with rounding from the Q2.16 spec, using a fixed `SPEC_FRAC = 16`,
  not `F_MAIN`.
- Low-bit casts must keep MSBs and round, not take the low bits (that is a
  modulo wrap).
- Identical rows across different generics are always a bug, never a result.
  `harvest.tcl` now checks for this.
- Any experiment ending with `SAT_COUNT > 0` is measuring clipping, not
  quantization. Check it every time.
- **admm_top defaults to ASYMMETRIC=1, USE_DSP_L2=1.** Every study build uses
  0/0. Any new wrapper must pass both, plus F_L1_P/F_BOX_P/F_L2_P, explicitly.
  Omitting them silently builds lanes 16/8/7: L1 still passes, Box/L2 fail.
- **Never edit admm_defs.vh to change width.** It stays at F_MAIN=16 so
  `build.bat` tests the F=16 vectors. Select other widths with
  `-verilog_define F_MAIN=<n>` (synthesis) or regenerate vectors to match.
- **A PASS from a path never exercised before is a zero until proven
  otherwise.** Missing .mem files synthesise ROM to 0 → solver "converges" in
  1 iteration → 0 == 0 reads as PASS. Empty SAIF → report_power silently goes
  vectorless. Guards exist for both; keep them.
- **Vivado/Windows tooling traps** (SAIF flow): Tcl eats backslashes — use
  forward slashes in every tool argument; .bat → .bat needs `call`; xelab needs
  `-debug typical` for log_saif; `-generic_top` escapes the top name and
  corrupts SAIF — pass config as quoted `-d "FM=9"` macros; never log `/*`.
- **LUT cells ≠ Slice LUTs.** `harvest.tcl` counts LUT cells (6308 / 3366);
  `report_utilization` gives physical LUTs (4673 / 2574, −44.9%). Anything
  compared with another paper uses `tools/util_table.py`. See COMPARISON.md §0.
- **SAIF power was measured at 50 MHz (20 ns),** not at Fmax. Energy/solve is
  frequency-independent; power is not. Always state the clock next to mW.
- **Binary over UART has no delimiter.** A payload byte can equal 0x0A. Read a
  fixed length.

