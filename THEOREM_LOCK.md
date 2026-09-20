# P0.2b — Theorem set, LOCKED 2026-09-04

Decision document. Inputs: `P0_RESULT.md`, `STATUS.md`, `RELATED_WORK.md`,
`SPRINT1_RESULT.md`. Every entry states what is claimed, what validates it,
and what must be said out loud.

---

## HELD-OUT TEST OF THE LOOP-GAIN FIT (2026-09-20) — READ FIRST

`model/margin.py` fits the loop-gain model exactly as published (20-trial
ensembles, seeds 7000+) and tests it on DISJOINT seeds (20000+, 25 trials),
plus three further seed sets for repeatability.

| operator | in-sample | **held-out** | seed-to-seed sd | largest instance share |
|---|---|---|---|---|
| L1  | 0.279 bits | **1.382 bits** | 0.593 bits | 68% of ensemble MSE |
| Box | 0.146 bits | **0.734 bits** | 0.156 bits | 19% |
| L2  | 0.061 bits | **0.046 bits** | 0.075 bits | 12% |

**Only the L2 loop-gain model generalises.** For L1 the ensemble mean is
essentially one outlier instance, and it moves 0.59 bits between seed sets --
MORE than the 0.34-bit LOO error the P0.1 result was claimed at. That fit was
fitting which seeds were drawn. **P0.1 ("d closes the L1 loop-gain term") is
RETRACTED**, and so is the Box d^2 form (P0.2b): 0.73 bits held out, 4.7x its
own seed noise, so it is over-fitted, not noisy.

The earlier LOO figures (0.340 / 0.234 / 0.031) were leave-one-CONDITION-out on
the SAME seeds, which is why they could not see this. Held-out seeds are the
test from now on.

A robust statistic does not rescue it. On the geometric mean of per-instance
gain, L1 is still 0.866 bits held out. For Box the geometric mean is
ILL-POSED: 16 of 720 instances have exactly zero error (everything clipped,
fixed == float bit for bit), so the result depends on how zeros are handled
(0.43 or 0.63 bits). An earlier in-chat claim that Box "generalises with the
geometric mean" came from one such handling and is withdrawn.

**What survives for L1 and Box:** the ZERO-PARAMETER resolvent predictor of
T2 (lane-width GAPS, 0.288 bits Box-L2, sign 8/8). It fits nothing, so it
cannot over-fit, and differences cancel the common noise.

### Per-instance margin (TODO item 3)

Signed error on held-out instances, bits of wordlength, + = model
UNDER-predicts (width too narrow):

| operator | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|
| L2 | -0.09 | +0.41 | +0.53 | **+0.66** | +0.73 |
| Box | -0.92 | +1.67 | +2.76 | +3.46 | +4.05 |
| L1 | -3.06 | +0.60 | +1.13 | +1.90 | +4.22 |

**Quotable margin: L2 only. Add 1 bit to the model's W* and 99% of held-out
instances are covered (worst observed +0.73).** For L1 and Box the quantiles
are margins on a model that does not generalise, so they are not a design
rule. Width selection for those lanes needs simulation -- which is what
chose and verified Q2.9 (bit-exact in gate-level sim and on the board).
State that as the method, not as a gap.

### The 0.5-bit criterion, justified (TODO item 2)

Li et al. (TRETS 2023) hold their SQNR model to < 1 dB, about 0.17 bits.
Three points, all measured:

1. **The like-for-like comparison is T1, and T1 meets Li's bar.** Li's
   quantity is an analytical noise model against bit-exact simulation for a
   fixed pipeline. Our counterpart is T1 at operator level: model/measured
   0.99, 1.00, 0.88, i.e. **0.007, 0.000, 0.092 bits**. All three are inside
   0.17. Say this first.
2. **A loop-level criterion cannot be tighter than the quantity's own
   repeatability.** The seed-to-seed sd of ensemble loop gain is 0.075 (L2),
   0.156 (Box), 0.593 (L1) bits. Below that a criterion is untestable. L2
   still clears Li's 0.17 bits held out (0.046).
3. **0.5 bits is the design-decision resolution.** Widths are integers; a
   predictor within half a bit selects the correct width or one adjacent to
   it, which simulation then settles.

The criterion stays at 0.5 bits for loop-level claims, is applied to
HELD-OUT data only, and is stated with the repeatability floor beside it.

### kappa term and outlier explanation for the T2 L1-Box residual (item 4)

`model/kappa_term.py`. The T2 predictor is 0.4-0.6 bits low on L1-Box and flat
in kappa, while the measured gap falls with kappa (-2.04 bits per unit).

- **K1/K2, parameter-quantisation terms — REFUTED.** Adding kappa's lattice
  error to L1 AND the bound's lattice error to Box (after alpha-normalisation
  the bound is not a power of two, so Corollary 1a's "Box has no theta term"
  does not hold) moves the error 0.355 -> 0.342 bits and predicts a kappa
  trend of -0.45 against the measured -2.04. Both terms are ~q^2/12 on
  average and cancel in the gap.
- **K3, outlier artefact — REFUTED.** Recomputing W* from geometric-mean
  error gives 0.363 bits and a kappa trend of -1.48. In THIS problem generator
  no instance dominates (10-20%, vs 68% in the loop-gain generator).

**The L1-Box residual is OPEN.** Two candidates tested, two refuted. Report it
as unexplained; do not guess.

## SECOND PROBLEM: LASSO (2026-09-20)

`model/lasso.py`, `model/gen_vectors_lasso.py`, `results/lasso.json`.
min ½‖Ax−b‖² + λ‖x‖₁ maps onto the UNCHANGED datapath: M = (AᵀA+ρI)⁻¹,
q = Aᵀb, L1 lane with κ = λ/ρ. N = 8, k = 2-sparse truth, Gaussian A, 20 dB.
Four predictions were registered in the script docstring before any run.

This matters beyond scope. On the MIMO workload the L1 lane has d ≈ 0
(`error_decomp.py`), so T1's (1−d) term was exercised for L1 only by
`annihilation.py`, which sweeps κ with κ placed on the lattice. LASSO gives
d = 0.62–0.77 natively, with κ wherever λ puts it.

| ID | Prediction | Result |
|---|---|---|
| P-L1 | T1/meas ∈ [0.9, 1.1] on the native LASSO v-distribution | **PASS**: 0.988, 1.028, 1.019, 0.981, 0.993 at λ/λmax = 0.05, 0.1, 0.2, 0.3, 0.5 (d 0.62–0.77; F = 6–12; 60 instances, m = 16). Classical q²/12 off by 1.6–2.7× |
| P-L2 | m = 32: F* ≤ 9; m = 6: F* > 9 (NMSE ≤ 1e-4) | **PASS**: m = 32 (‖M‖₂ 0.74) F* = 8 at every λ; m = 16 (0.87) 9; m = 8 (0.99) 9–11; m = 6 (1.00) 10–11. No saturation anywhere |
| P-L3 | support at F* matches double precision on ≥ 99% of instances | **FAILED as registered**: 90–100% per cell |
| P-L4 | RTL bit-exact on LASSO vectors | **PASS** at F_MAIN = 16 and 9, three instances (m = 32, 16, 8), unmodified RTL (`build.bat 0 lasso`) |

**P-L3, post-hoc — say it is post-hoc.** `python model/lasso.py --e3`, written
after the failure. All 11 disagreeing coefficients across the 12 cells are
≤ 2 LSB of F* in magnitude (82% ≤ 1 LSB): the two solvers disagree about
values at the resolution limit of the format, i.e. threshold ties. That
characterises the failure; it does not rescue the prediction. The paper
reports P-L3 as failed, then the characterisation.

**Why the classical ratio is not 1/(1−d).** 1/(1−d) is 2.7–4.4 here; the
classical model misses by less because κ is off-lattice, and the κ lattice
error (a T1 θ-term) adds to the measured error. T1 includes it; q²/12 does not.

**P-L2 reading.** Width need tracks ‖M‖₂ → 1/ρ as the problem loses rows, the
same resolvent story as T2. It is a trend across 12 cells at 40 instances, not
a fitted law, and F* is not monotone inside m ≤ 8. Do not quote a formula.

**Ground truth vs double precision.** Instance m = 8 (seed 5102) recovers
support {3,5} against truth {5,6} — in double precision too. That is LASSO at
m = 8, not quantization. Every comparison above is against double-precision
LASSO on the same instance, never against x0.

Claimable: T1 validated on a second problem at native high d with off-lattice
κ; the design point (Q2.9) carries over to well-determined LASSO (m ≥ 16) and
needs 1–2 more bits as m → N; the hardware runs it bit-exact unchanged.
Not claimable: support fidelity ≥ 99%; any width formula in m.

---

## SCOPE LIMIT FOUND BY ADVERSARIAL TEST (2026-09-06) — READ FIRST

`model/adversarial.py` attacks the fitted loop-gain model with Kinsman &
Nicolici's own method (eigenvector-aligned right-hand sides) plus a greedy
search maximising model error. Errors are reported SIGNED, because the sign is
the whole story: positive means the model UNDER-predicts error, so wordlengths
chosen from it are TOO FEW.

**The model under-predicts, and random instances already break it.**

| operator | worst under-prediction, RANDOM rhs | worst, adversarial |
|---|---|---|
| L1 | **+7.58 bits** | +11.43 bits |
| Box | +2.16 bits | +3.43 bits |
| L2 | +0.60 bits | +2.25 bits |

**Diagnosis, and it is not an exotic corner.** `loop_gain.py` fits on 20-trial
ENSEMBLE AVERAGES at each conditioning point. The published figures (0.834 /
0.399 / 0.031 bits) are therefore ENSEMBLE-LEVEL quantities. Per-instance
scatter is far larger, which the adversarial search then exploits but does not
create. A per-instance refit gives 0.979 / 0.611 / 0.339 bits before any attack.

**Consequence for the claim.** The loop-gain relation is a DESIGN-SPACE
EXPLORATION tool that predicts the mean loop gain of an ensemble at a given
conditioning. It is NOT a per-instance safety guarantee and must never be
described as one. Every reported bit figure must say "ensemble mean over N
trials at fixed conditioning".

**What this does NOT invalidate.** The headline hardware result stands: the
Q2.9 design point was chosen with model guidance and then VERIFIED bit-exact
against the golden model on routed silicon. The model informed the choice;
measurement confirmed it. That is the correct division of labour and should be
stated as the methodology, not hidden.

**What the paper must now say.** Wordlength selection from this model requires
an empirical margin, and we can quote one: the measured per-instance
under-prediction. Alternatively, a guaranteed bound is available from the prior
art (Jerez et al.; Kinsman & Nicolici) at the cost of the conservatism our
model exists to avoid. Present that as a trade-off the designer chooses, not a
gap we overlooked.

**Honesty note.** The first run of this script reported catastrophic failure
across the board. That was a harness bug: `system_cond` returns `a` as a scale
factor (<=1) applied to both q and the lane thresholds, and the first version
treated it as an amplitude while also dropping the observation noise. The
numbers above are from the corrected harness. The bug is documented in
`model/adversarial.py` so it is not reintroduced.

---

## TIER 1 — CLAIMED AS THEOREMS (derived AND validated)

### T1. Operator error decomposition — the core result
E��e_P‖² = (|Dᶜ|/n)·L²·q²/3 + ‖∂P/∂θ‖²·q_θ²/3, i.e. the degenerate set
annihilates its share of the injected error.

Validation (`error_decomp.py`): T1/measured = **0.99 (L1), 1.00 (Box)**.
Classical q²/12 is off by 3–4× typically and 900× at d=0.999.

**Second problem (2026-09-20):** on LASSO's native distribution
(d 0.62–0.77, κ off-lattice) T1/meas = 0.981–1.028 across five λ; see
"SECOND PROBLEM: LASSO" above.

**Caveat that must be stated: L2 gives 0.88, a 12% miss.** L2 has d=0, so the
annihilation term is inactive and the miss lies in the θ term (γ coefficient
quantization, which Corollary 1a says is *not* attenuated). So the annihilation
mechanism is validated; the coefficient-quantization magnitude is not, to
better than ~12%. Say this rather than quoting "0.99–1.00" and hoping.

**Positioning (mandatory).** Jerez, Goulart, Richter, Constantinides, Kerrigan
& Morari (arXiv:1303.1090) already observed that the proximal step scales
error by a diagonal matrix with entries in [0,1], then DISCARDED the factor to
keep their bound conservative. T1 quantifies exactly that factor as (1−d) and
validates it predictively. Claim the quantification, not the observation.

### P1. Range feasibility and the penalty lower bound
ρ ≥ 2^−(I−1) from weight representability.
Validated BEFORE it was written: I=2 predicts ρ ≥ 0.5; measured max|M| = 2.116
at ρ=0.125 (infeasible), 1.117 at ρ=0.5 (feasible). Say that it was
pre-registered — it is the cleanest methodological point in the paper.

### T4. Profitability condition — the headline
Asymmetric lane allocation is profitable iff the area saved exceeds the cast
overhead; when no lane crosses the macro threshold the quadratic term vanishes
and asymmetry is provably net-negative.

**Now strongly validated.** Measured asymmetry cost is **+4.3% LUT at BOTH
F_MAIN=16 and F_MAIN=9** — identical to one decimal, two independent widths —
with no dynamic-power benefit (three measured null pairs) and no consistent
Fmax effect. Independently corroborated in Wu et al. 2022 Table 1 (their ADMM
FXP20→24 uses 6807 LUT vs consistent FXP24's 6775).

**Constraint:** the macro-threshold mechanism is Li et al. / Constantinides
prior art per HANDOFF. Cite it; do not present the threshold as ours. What is
ours is the cast-overhead accounting and the measured net-negative result.

---

## TIER 2 — EMPIRICAL, SCOPED BY THE HELD-OUT TEST

### Loop gain
- **L2:** log G = a*log(R) + c with R the loop resolvent. Held-out error
  0.046 bits, inside even Li et al.'s 0.17-bit bar. Per-instance p99 +0.66
  bits: **add 1 bit**. CLAIMED.
- **L1, Box:** the fitted forms (d, d^2) do NOT generalise to held-out seeds
  (1.38, 0.73 bits). RETRACTED as models. What is claimed for them is
  qualitative -- loop gain grows with conditioning and tracks the resolvent --
  plus the zero-parameter T2 gap predictor.
- No mechanism is claimed for any sign difference (churn refuted).

## TIER 3 — DEMOTED TO DISCUSSION

### T2. Ordering — RESTATED after its falsifier (2026-09-20)

**Correction.** The earlier demotion said measurement showed a fixed ordering.
That was read from a single-point table. `results/ordering_sweep.json` already
showed crossovers across conditioning, and `model/t2_crossover.py` (continuous
W*, 14 sweep points, 30 trials each, zero saturation) confirms them: Box - L2
goes from -0.33 bits at cond=2 to +2.33 at cond=1000, crossing between cond 10
and 20. **T2's headline -- no fixed ordering -- HOLDS.**

**T2's stated mechanism FAILS.** Operator coefficient alone,
dW = 0.5*log2(A_a/A_b):

| pair | mean abs error | sign right |
|---|---|---|
| L1 - Box | 0.355 bits | 12/12 |
| Box - L2 | 1.214 bits | **2/8** |
| L1 - L2 | 1.514 bits | **0/14** |

**Restated mechanism, zero fitted parameters.** Multiply by the loop resolvent
R = ||(I-T)^-1||, computed from M with prox gain gamma for L2 and 1 for L1/Box:
dW = 0.5*log2(A_a*R_a / (A_b*R_b)).

| pair | mean abs error | sign right |
|---|---|---|
| L1 - Box | 0.355 bits | 12/12 |
| Box - L2 | **0.288 bits** | **8/8** |
| L1 - L2 | 0.621 bits | 12/14 |

Box-L2 crossover predicted near cond=20; measured between 10 and 20. L2's
contraction pins its resolvent (2.1 -> 3.2 over three decades of conditioning)
while L1/Box resolvents grow 2.7 -> 200, so the contractive lane gets
relatively cheaper as the problem hardens.

**CLAIM:** lane-width ordering = operator coefficient x loop resolvent,
predicted with no fitted parameters. The operator coefficient alone does not
determine it -- the paper's operator/loop split, shown on ordering as well as
error magnitude.

**Caveats that must be stated.**
- L1-L2 is 0.621 bits, outside 0.5, and misses the two smallest gaps
  (cond 2, 3) in sign.
- L1-Box is under-predicted by ~0.4-0.6 bits and the predictor is flat in
  kappa while the measurement is not (d_L1 ~ 0 across that sweep). Corollary
  1a's kappa-quantisation term, omitted from A_op, is the likely cause.
  UNTESTED.
- The loop_gain.py FITTED exponents (1.06 / 0.51 / 0.96) make Box-L2 WORSE
  (1.051 bits, sign 4/8). The fitted Box exponent does not transfer to this
  problem generator; the zero-parameter resolvent does. Consistent with the
  ensemble-only scope limit on the fitted loop-gain model.
- W* here is LANE precision with F_MAIN fixed at 16, not main-datapath width.

### T5. Composition — DEMOTED (this was predicted)
Sprint 1 falsifier: 2.509 bits mean error against a 0.5-bit criterion, worse
than the classical model's own failure in places. THEORY_PLAN flagged T5 as
"the one most likely to fail — do not force it." It failed. Demote to
discussion, exactly as planned, and note that the negative result is what
relocated contraction from the operator to the loop.

---

## TIER 4 — CANNOT BE CLAIMED YET (blocked on a run, not a decision)

### T3. Fabric cost model — QUADRATIC FORM REJECTED, LINEAR FORM VALIDATED (2026-09-04)

Held-out test run. Fit on the three no-cast points (lane width = F_MAIN):
16 -> 269.9, 10 -> 159.0, 9 -> 129.0 LUT/lane. Predict lane 8 (actual 122.0).

| form | fit | predicts W=8 | error | verdict |
|---|---|---|---|---|
| quadratic | exact (3pts/3params) | 95.7 | -21.6% | **FAIL** (10% bar) |
| linear | 3.0% max residual | 114.3 | -6.3% | **pass** |

Fitted a is NEGATIVE (-1.646), i.e. concave: slope falls from 30 LUT/bit
(9->10) to 18.5 (10->16). A fabric-multiplier area law must be convex.

**Resolution.** The 166-vs-35 LUT figure was measured on the gamma multiplier
in ISOLATION, where the quadratic law does hold (4.74 vs 4 predicted). At
whole-lane granularity the multiplier is a small share -- L1 and Box have no
multiplier at all -- so casts, compares and saturating adds dominate and the
total is linear. The W^2 term is NOT refuted; it is undetectable at lane
granularity on this design.

**CLAIM: A_lane(W) = b*W + c, b ~ 19.6 LUT/bit, validated out-of-sample at
-6.3%.** Keep the quadratic term only for the isolated multiplier, and state
which granularity each applies to.

**This STRENGTHENS T4.** T4 says asymmetry pays only when the quadratic term
is active. With lane area linear, narrowing saves b*dW -- linear and small --
so cast overhead wins, which is exactly the measured +4.3% penalty. T4's
derivation now rests on a form that survived its own falsifier.

**c_cast measured directly (bonus).** The two lane-8 builds differ: 122.0
LUT/lane at F_MAIN=10 vs 127.5 at F_MAIN=16 -- same lane width, different cast
depth -> **c_cast ~ 0.9 LUT/bit/lane**. Previously inferred, now measured.

### T3 — superseded original text
A(W) = a·W² + b·W + c_cast + c₀ is currently **fitted and reported on the same
points**, which the project's own rule forbids. THEORY_PLAN specifies the
falsifier: synthesise a held-out width and check prediction within ~10%. It
was never run.

**This is now cheap.** The six-build sweep spans lane widths 16, 10, 9, 8 and
`run_ooc.tcl` emits a `LUT prox` column per build. Fit on three widths, predict
the fourth. If it misses by >10% the quadratic form is wrong and T4 — which
substitutes T3 — loses its derivation while keeping its measurement.

**T4's empirical result stands regardless.** Only its *derivation* depends on
T3, and the +4.3% measurement does not.

---

## What the paper claims, in one paragraph

An error model in which the proximal operator's degenerate set annihilates a
measurable fraction (1−d) of injected quantization noise, validated to 0.99–1.00
against bit-exact simulation for L1 and Box (12% miss on L2's coefficient term);
a pre-registered range-feasibility bound on ρ; a measured demonstration that
per-operator asymmetric wordlength allocation is net-negative in fabric, +4.3%
area at two independent widths with no power or frequency compensation; a
loop-gain model that generalises for the contractive L2 lane only (held-out
0.046 bits, 1-bit margin covers 99% of instances), with the L1/Box fits
retracted after a held-out test; and a fully measured hardware characterisation —
SAIF power, swept Fmax, bit-exact gate-level validation — of six configurations
on routed Artix-7 silicon. A second problem, LASSO, runs bit-exact on the
unchanged hardware and reproduces T1 (0.98–1.03) at native d up to 0.77.

## What the paper must NOT claim
- LASSO support fidelity ≥ 99% (P-L3 failed; mismatches are ≤ 2 LSB,
  a post-hoc characterisation). Any width formula in m.
- That the L1 or Box loop-gain FITS generalise. They fail held-out seeds.
- Any bit figure without saying whether it is in-sample, LOO or held-out.
- A mechanism for the T2 L1-Box residual (two candidates refuted).
- "First error model for fixed-point ADMM." Jerez et al. 2013 have one.
- A mechanism for the L1/Box sign difference. Tested and refuted.
- A unified functional form across operators. d vs d² is significant.
- The DSP/macro operand-width threshold as a contribution. Prior art.
- "Analytic instead of search." Prior art.
- T3's cost model as validated, until the held-out width is run.
- T2's ordering condition in any form.
