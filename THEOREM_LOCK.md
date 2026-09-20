# P0.2b — Theorem set, LOCKED 2026-09-04

Decision document. Inputs: `P0_RESULT.md`, `STATUS.md`, `RELATED_WORK.md`,
`SPRINT1_RESULT.md`. Every entry states what is claimed, what validates it,
and what must be said out loud.

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

## TIER 2 — CLAIMED AS AN EMPIRICAL MODEL, NOT DERIVED

### Loop-gain relation (new; not in the original THEORY_PLAN)
log G = a·log(1/(1−‖M‖₂)) + b·R_op + c, with R_L1 = d, R_Box = d², R_L2 = none.
LOO cross-validated: 0.340 / 0.234 / 0.031 bits, all inside the 0.5-bit bar.
`d` survives the conditioning confound (log cond alone gives LOO 1.237, worse
than baseline).

**Claimed as fitted and cross-validated. NO mechanism is claimed.** The churn
hypothesis was tested and refuted (`box_form.py`: Box churns MORE than L1, and
both are ~frozen). The L1/Box sign difference follows from d's opposite
monotonicity with conditioning, not from two mechanisms. Box's d² beats d at
p<0.05 but several forms were tried first, so present the exponent as fitted.

---

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
cross-validated empirical loop-gain model with a per-operator degeneracy term
and no mechanism claimed; and a fully measured hardware characterisation —
SAIF power, swept Fmax, bit-exact gate-level validation — of six configurations
on routed Artix-7 silicon.

## What the paper must NOT claim
- "First error model for fixed-point ADMM." Jerez et al. 2013 have one.
- A mechanism for the L1/Box sign difference. Tested and refuted.
- A unified functional form across operators. d vs d² is significant.
- The DSP/macro operand-width threshold as a contribution. Prior art.
- "Analytic instead of search." Prior art.
- T3's cost model as validated, until the held-out width is run.
- T2's ordering condition in any form.
