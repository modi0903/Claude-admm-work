# Theory Plan — Phase-Reconfigurable ADMM Accelerator

Everything here is constrained by what the silicon and the bit-exact model
already told us. No result is planned that the data contradicts.

---

## 0. What the measurements force us to accept

These are not negotiable. Every proof below must be consistent with them.

| # | Measurement | Consequence for the theory |
|---|---|---|
| M1 | Fabric: prox array 2720 → 1712 LUTs (−37.1%). With DSP: 1392 → 1432 (+2.9%) | Area saving is conditional on the arithmetic being in fabric. Any theorem predicting unconditional saving is false. |
| M2 | Fabric multiplier: 166 LUTs @18×18, 35 @9×9, ratio 4.74 (W² predicts 4.00) | Lane area is dominated by a quadratic multiplier term. |
| M3 | Casts cost ~40 LUTs/8 lanes with no offsetting saving under DSP | Narrowing has a fixed overhead that must appear in the cost model. |
| M4 | Required lane widths are 6–9 fractional bits, not 16 | The Q2.16 baseline is over-provisioned; the "uniform 18-bit baseline" is a weak strawman unless justified. |
| M5 | Ordering W\*_L1 > W\*_Box ≥ W\*_L2 fails under NMSE at every threshold; holds under abs-error in some regimes; Box is consistently *cheapest* | The ordering is not a fixed inequality. It is a function of problem statistics. |
| M6 | L1 active-set misclassification = 0 for F ≥ 4 | The old Theorem 2 mechanism is not operative. Its premise must go. |
| M7 | Binding overflow is `w = q + ρ(z−u)`, peak 3.80 unscaled | Range constraint is on the pre-combination, not on the L2 lane. |
| M8 | max\|M\| ≤ 1/ρ; measured 2.116 at ρ=0.125, 1.117 at ρ=0.5 | A *lower* bound on ρ exists, derived from M's spectrum — not from γ. |

---

## 1. The reframe

**Old claim.** Proximal operators have intrinsically different precision needs;
exploit this to prune; get 52.3%.

Dead. M5 kills the fixed ordering, M6 kills its mechanism, M1 kills the
unconditional area claim, and the 52.3% never came from synthesisable RTL.

**New claim.** Two analytic models — one for how much precision each proximal
operator needs, one for what a bit costs in a given fabric — compose into a
closed-form predictor of whether asymmetric wordlength allocation is profitable
at all, and by how much. The predictor is validated against routed silicon, and
it correctly predicts both the 37.1% win in fabric and the 2.9% loss on hard
macros.

This is stronger than the old claim because it says **when not to do this**,
which is the part practitioners actually need and which the WLO literature —
being search-based — cannot express.

---

## 2. Proof inventory

Dependency order. Each has a stated *purpose*, *method*, and *falsifier*.

### Lemma 1 — Homogeneity of the fixed-point recursion
**Statement.** For P ∈ {Π_[lo,hi], S_κ, γ·}, scaling (q, κ, lo, hi) by α > 0
scales (x, z, u) by α and leaves the iterate trajectory, iteration count and
convergence behaviour identical. M is unchanged.

**Method.** Direct: show each prox is positively homogeneous of degree 1 under
simultaneous scaling of its parameters, then induct over the three ADMM updates.

**Purpose.** Licenses the α-normalisation that made every experiment valid
(M7). Without it, the scaling looks like a fudge; with it, it's exact.

**Falsifier.** Any operator whose parameters don't scale (e.g. a fixed
saturation unrelated to the signal). State the class it covers and stop there.

---

### Lemma 2 — Neighborhood convergence under bounded prox error
**Statement.** If the z-update is computed as ẑ = P(v) + e_k with
sup_k‖e_k‖₂ ≤ ē, then ADMM iterates converge to a ball around the exact
solution of radius C·ē, with C depending on ρ and the spectrum of M.

**Method.** Do **not** reprove this. Cite and adapt: Eckstein & Bertsekas
(1992) for summable-error convergence, and the perturbed/inexact ADMM
neighborhood results. Our contribution starts at Theorem 1, not here.

**Purpose.** Converts "quantization error" into "distance from optimum", which
is the only way a wordlength bound means anything.

**Falsifier.** None expected; this is textbook. Risk is misciting — check the
exact hypotheses (convexity, closedness, ρ > 0) hold for all three operators.

---

### Theorem 1 — Operator error decomposition *(THE CORE RESULT)*
**Statement.** Let P_θ be a proximal operator with parameter θ, evaluated at
fractional wordlength W (step q = 2^−W). Partition the input index set into
the **degenerate set** D (where ∂P/∂v = 0 — the output is independent of the
input) and its complement Dᶜ. Then

  E‖e_P‖² = (|Dᶜ|/n)·L²·q²/3 + ‖∂P/∂θ‖²·q_θ²/3 + O(q³)

where L is the local Lipschitz gain on Dᶜ and q_θ the parameter step.

**Method.**
1. Model input quantization as e_v ~ U(−q/2, q/2), i.i.d., zero mean,
   variance q²/12 per element (fix the factor-of-2 error in the old Theorem 1).
2. On D, P(v + e_v) = P(v) exactly — the perturbation is annihilated.
   *This is the whole point and it is elementary to prove per operator.*
3. On Dᶜ, first-order expansion gives L·e_v.
4. Parameter quantization contributes independently.
5. Sum variances (independence), take expectation over the index partition.

**Purpose.** Replaces both the vacuous old Theorem 2 (active-set floor) and the
hand-waved old Theorem 3. It is the single mechanism that explains all three
operators *and* their regime dependence.

**Why it's defensible.** It's a variance calculation, not an inequality chain.
Each term is separately measurable in the bit-exact model.

**Falsifier.** Measure E‖e_P‖² directly in `fxp_admm.py` per operator per W and
check it tracks the formula. If the (|Dᶜ|/n) scaling doesn't appear, the
theorem is wrong. **Run this before writing a word of it.**

---

### Corollary 1a — Per-operator instantiation
Apply Theorem 1 to each lane:

| operator | D (degenerate set) | L on Dᶜ | θ term |
|---|---|---|---|
| Box Π_[lo,hi] | clipped components, \|v\| ≥ hi | 1 | none (bounds are exact powers of 2 in Q-format) |
| L1 S_κ | zeroed components, \|v\| ≤ κ | 1 | ∂/∂κ = 1 on Dᶜ → **doubles** the Dᶜ variance |
| L2 γ· | ∅ | γ | ∂/∂γ = v → E[v²]·q_γ²/3, **not attenuated** |

Immediate predictions:
- Box is cheapest **when its clipped fraction is large** (BPSK detection near
  the bounds → most components clip → most error annihilated). Matches M5.
- L1 costs ≈ ½ bit more than Box at equal degenerate fraction, plus more
  whenever κ is small (few components zeroed → \|D\| small). Matches M5.
- L2 has a **floor** from coefficient quantization that contraction does not
  attenuate. This is exactly what the old theory missed and why L2 never came
  out cheapest. Matches M5.

---

### Theorem 2 — The ordering is a function of problem statistics
**Statement.** Define the degenerate fractions d_Box = |D_Box|/n and
d_L1 = |D_L1|/n. Then

  W\*_Box < W\*_L1  ⟺  d_Box > d_L1 + (½ bit correction)

and W\*_L2 is bounded below independently of γ by the coefficient term. No
fixed ordering among the three holds for all (κ, γ, box width, channel
conditioning).

**Method.** Set each operator's E‖e_P‖² equal to the tolerance implied by
Lemma 2 and solve for W.

**Purpose.** This is the honest replacement for the old Theorem 3. It *derives*
the regime dependence we measured instead of asserting an inequality that
fails.

**Presentational note.** Do not frame this as "our earlier ordering was wrong."
Frame it as: the ordering is a *consequence* of operator geometry and problem
statistics, and we give the condition. That is a stronger paper and it is true.

**Falsifier.** The κ / γ / box-width / conditioning sweep must trace the
predicted crossover. `sweep_ordering.py` already runs it; add d_Box and d_L1 as
measured outputs and check the crossover lands where predicted.

---

### Proposition 1 — Range feasibility and the penalty lower bound
**Statement.** With I integer bits (range ±2^(I−1)):

(a) *Weight feasibility.* max\|M_ij\| ≤ ‖M‖₂ = 1/(λ_min(HᵀH) + ρ) ≤ 1/ρ.
    Requiring M to be representable gives **ρ ≥ ρ_min = 2^−(I−1)**.

(b) *Pre-combination feasibility.* ‖w‖_∞ ≤ ‖q‖_∞ + ρ(‖z‖_∞ + ‖u‖_∞) < 2^(I−1),
    with ‖z‖_∞ bounded by the operator (exactly `hi` for Box) and ‖u‖_∞ bounded
    by dual boundedness.

**Method.** (a) is a one-line spectral bound. (b) is the triangle inequality
plus per-operator range bounds, closed by Lemma 1's α.

**Purpose.** Replaces the broken old Proposition 1 wholesale. Note it *recovers
the original intuition* — a lower bound on ρ — by a completely different and
correct route. The old derivation had γ = ρ/(ρ+λ) increasing in ρ and then
called the resulting upper bound a lower bound.

**Falsifier.** Already validated: I = 2 predicts ρ ≥ 0.5; measured max\|M\| =
2.116 at ρ = 0.125 (infeasible) and 1.117 at ρ = 0.5 (feasible). **This
prediction was confirmed before the theorem was written.** Say so.

---

### Theorem 3 — Fabric cost model
**Statement.** Lane area in LUTs at operand width W:

  A(W) = a·W² · 1[multiplier in fabric] + b·W + c_cast + c₀

with a ≈ 0.5 LUT/bit² measured, and the indicator collapsing to 0 whenever
W ≤ W_macro and the tool infers a hard macro.

**Method.** Fit against the four-build sweep (M2), then validate by predicting
a held-out width. **Do not fit and report on the same points.** Synthesise a
third width (e.g. 13 bits) and check the model predicts it.

**Purpose.** Turns "narrower is smaller" from folklore into a number.

**Falsifier.** The held-out width. If A(13) is mispredicted by more than ~10%,
the quadratic form is wrong — likely because carry-chain and cast terms don't
separate cleanly.

---

### Theorem 4 — Profitability condition *(THE HEADLINE)*
**Statement.** Asymmetric allocation of lane widths {W_op} against a uniform
baseline W_max is profitable iff

  Σ_op [ a(W_max² − W_op²)·1[fabric] + b(W_max − W_op) ]  >  Σ_op c_cast

On a device where every W_op ≤ W_macro, the indicator vanishes for all lanes,
the quadratic term disappears, and the condition **cannot** be met — asymmetric
allocation is provably net-negative.

**Method.** Substitute Theorem 3 into the difference of two designs. Two lines.

**Purpose.** This is the paper's contribution in one inequality. It predicts
+37.1% and −2.9% from the same formula with the indicator flipped.

**Falsifier.** The four-build table. Already consistent. Strengthen by
predicting a *fifth* configuration before synthesising it.

---

### Theorem 5 — Composition
Feed W\*_op from Theorem 2 into Theorem 4 to get predicted area saving from
problem statistics alone, with no synthesis in the loop. Compare against the
measured 37.1%.

**Purpose.** This is what makes it *co-design* rather than two separate
observations. It's also the strongest thing in the paper if it lands within a
few percent.

**Risk.** This is the one most likely to fail. If prediction and measurement
disagree badly, demote it to a discussion section and let Theorems 2 and 4
stand independently. **Do not force it.**

---

## 3. Derivation procedure — order of operations

Strict order. Do not start writing LaTeX until step 4.

1. **Instrument Theorem 1 numerically first.** Add per-operator
   E‖e_P‖² measurement to `fxp_admm.py`, split into the D and Dᶜ contributions,
   and the θ term. Confirm the three-term decomposition holds before proving it.
   *If the decomposition doesn't appear in the data, stop and rethink.*
2. **Measure d_Box, d_L1** across the sweep, confirm the Theorem 2 crossover.
3. **Re-derive the lane widths** from Theorem 2 + the measured tolerance.
   Replace 18/10/9 with the justified triple. Re-run synthesis on those.
4. **Fit Theorem 3**, then hold out a width and validate.
5. **Write the proofs.** In order: L1, L2 (cite), T1, C1a, T2, P1, T3, T4, T5.
6. **Re-run everything end to end** on the final widths and regenerate every
   number in the paper from one scripted pass.

Rule for the whole project: **no number enters the manuscript that isn't
produced by a script in this repo.** That is how the 52.3% happened.

---

## 4. Paper flow

| § | Content | Source |
|---|---|---|
| I | Intro: WLO is search-based, slow, gives no *when-not-to* guidance | lit review |
| II | Phase-reconfigurable MIMO pipeline; why one IP time-multiplexes three operators; why an N×N array serves N **users** not N antennas | architecture |
| III | Error model: L1, L2, **T1**, **C1a**, **T2** | new theory |
| IV | Range & feasibility: **P1** (both parts) | new theory |
| V | Cost model & profitability: **T3**, **T4**, **T5** | new theory |
| VI | Architecture: asymmetric prox unit, weight-stationary array, saturating datapath, the cast overhead as a first-class cost | RTL |
| VII | Validation: bit-exact model vs RTL; wordlength sweep vs T2; four-build synthesis vs T4; BER vs SNR; throughput/area vs TASER | measurements |
| VIII | Discussion: the negative result, and what it implies for ASIC vs DSP-FPGA | — |

Note §V before §VI: the cost model motivates the architecture, rather than the
architecture being presented and then justified after the fact.

---

## 5. Claims and defenses

### Claim 1 — Proximal operator precision is governed by the *degenerate set*, not by contraction
**Defense.** Theorem 1, validated by direct measurement of the error
decomposition.
**Anticipated attack.** "This is just standard quantization noise analysis."
**Response.** The novelty is the annihilation term: on D the operator destroys
the perturbation exactly, so effective noise power scales with |Dᶜ|/n. Standard
analyses assume every element contributes q²/12. Show the measured gap.

### Claim 2 — No fixed wordlength ordering exists; we give the condition
**Defense.** Theorem 2 plus the four-way sweep showing the crossover.
**Anticipated attack.** "Then the reconfigurable hardware can't be sized."
**Response.** It can — sized for the *worst case over the operating envelope*,
which Theorem 2 makes computable in closed form instead of by search. That is
the practical contribution.

### Claim 3 — Asymmetric pruning pays only when arithmetic is in fabric
**Defense.** Theorem 4 plus the four-build table: +37.1% / −2.9% from one
formula.
**Anticipated attack.** "This is a Vivado inference artifact, not a result."
**Response.** Correct, and that is the point — it is a *property of the target*,
which is exactly what a co-design methodology must account for. We control for
it explicitly with `USE_DSP_L2` rather than letting the tool decide silently.
This is the strongest defense in the paper: we found the confound and isolated
it.

### Claim 4 — Bit-exact model / RTL equivalence
**Defense.** Both builds pass element-wise against the golden model for all
three operators. Cheap to state, and it is what makes every other number
credible.

### Claim 5 — Competitive area/throughput
**Defense.** Deferred. Needs Fmax sweep and Mb/s normalisation before it can be
claimed at all. **Do not write this section until §7 items 3–4 are done.**

---

## 6. Threats to the paper

| Threat | Severity | Mitigation |
|---|---|---|
| Reviewer: "WLO is a solved, mature field" | high | Position against *search-based* WLO; our contribution is closed-form + the profitability condition, which search cannot express |
| Theorem 5 fails to compose | medium | Demote to discussion; T2 and T4 stand alone |
| Small array (N=8) reads as toy | medium | N is **users**, not antennas — 8 users × 32+ BS antennas is a real massive-MIMO config. Say it in §II, not in rebuttal |
| Real-valued only | medium | State the real-valued equivalent model explicitly; note complex doubles N |
| Fmax ~59 MHz vs TASER 232 MHz | high | Sweep the constraint; report throughput/area, not raw Fmax. If it stays low, own it as an edge/low-power operating point |
| Power numbers are vectorless | low | Regenerate from SAIF |

---

## 7. Immediate next actions

1. Instrument the Theorem 1 error decomposition in `fxp_admm.py`. **Blocks all
   theory work.**
2. Add d_Box / d_L1 measurement to `sweep_ordering.py`; locate the crossover.
3. Re-derive lane widths from Theorem 2; re-run the four-build synthesis on the
   justified widths.
4. Fmax sweep (tighten the constraint until failure) → real throughput.
5. SAIF-based power.
6. BER vs SNR, final widths.
7. Only then: write.

---

## APPENDIX A — Theorem 1 validation (RUN, PASSED)

`model/error_decomp.py` and `model/annihilation.py`.

### A.1 Three-term decomposition at the operating point

38,400 samples of v = x+u harvested from float ADMM, lane swept F = 4..14.
Reference is P_float applied to the same Q2.16 input with exact parameters, so
parameter quantization registers as lane error.

| operator | d = \|D\|/n | T1 pred / measured | standard model / measured |
|---|---|---|---|
| L1 soft-threshold | 0.000 | **0.99** | 0.61 |
| Box projection | 0.183 | **1.00** | 0.95 |
| L2 ridge scaling | 0.000 | **0.88** | **0.21** |

The standard flat-q²/12 model is wrong by 4.8x for L2. Theorem 1 is within 12%
there and within 1% for L1 and Box.

For L2 the discrepancy is entirely the coefficient term: contraction attenuates
the *input* noise by gamma, but gamma's own quantization error is multiplied by
v and is not attenuated at all. That is the term the original manuscript's
"strict contraction implies minimum wordlength" argument omitted, and it is why
L2 never measured as the cheapest lane.

### A.2 Annihilation — the central mechanism (decisive test)

Parameter swept so d ranges over [0, 1], with parameters snapped to the lane
lattice to zero the theta term and isolate annihilation. F = 8, so the standard
model predicts a flat 1.2716e-06 at every d.

| d | L1 measured MSE | (1-d)q²/12 | | d | Box measured MSE | (1-d)q²/12 |
|---|---|---|---|---|---|---|
| 0.000 | 1.283e-06 | 1.272e-06 | | 0.000 | 1.283e-06 | 1.272e-06 |
| 0.172 | 1.069e-06 | 1.053e-06 | | 0.120 | 1.132e-06 | 1.119e-06 |
| 0.485 | 6.687e-07 | 6.543e-07 | | 0.515 | 6.146e-07 | 6.172e-07 |
| 0.880 | 1.510e-07 | 1.525e-07 | | 0.828 | 2.145e-07 | 2.188e-07 |
| 1.000 | **0.000** | **0.000** | | 0.999 | 1.408e-09 | 1.351e-09 |

Over d in [0.12, 0.88]:

| | T1 / measured | standard / measured |
|---|---|---|
| L1 | **0.991** | 3.838 |
| Box | **1.004** | 3.040 |

At d = 1 the measured error is **exactly zero**. The operator annihilates the
perturbation completely. The standard model still predicts 1.27e-06 there, and
is wrong by up to 900x at d = 0.999.

**Theorem 1 is validated. Write it.**

### A.3 Two findings that came out of the validation

**Design rule — parameters must lie on the lane lattice.** A Box bound or L1
threshold that is not a multiple of the lane's quantization step contributes a
constant error on *every* degenerate element, exactly cancelling the benefit of
degeneracy. In the first run, alpha-scaling put the bound off-lattice and the
Box annihilation benefit vanished entirely. This is a free, actionable result:
constrain alpha to a power of two.

**Revised explanation of why L1 is expensive.** Not active-set misclassification
(measured at zero, M6). At the operating point d_L1 = 0.000 — the threshold
kappa = 0.1 is far below the signal level, so *nothing* is zeroed and there is
no annihilation at all. The remaining gap to Box is the kappa quantization term
on D^c. This predicts that placing kappa on the lattice should make L1 as cheap
as Box at equal d. **Test this next — it is a strong, cheap, falsifiable
prediction and it would be the first design rule the theory produces.**

### A.4 Consequence for Theorem 2

The ordering is now fully derived rather than asserted:

  W\*_op = ½ log₂ [ ( (1-d_op)(L_op² q²/12 + theta terms on D^c)
                     + d_op (theta terms on D) ) / tolerance ]

The measured ordering (Box cheapest, L1 and L2 comparable) follows directly
from d_Box = 0.183 > d_L1 = 0.000 together with L2's un-attenuated coefficient
term. No fixed inequality among the three survives, exactly as Theorem 2 states.

---

## APPENDIX B — The lattice rule (RUN, PASSED)

`model/lattice_rule.py`. Tests the prediction that fell out of A.3: L1's extra
cost over Box is threshold quantization, not active-set misclassification.

### B.1 Operator level, F=8

| kappa | d | MSE on-lattice | MSE off-lattice | ratio | MSE Box, **same d** |
|---|---|---|---|---|---|
| 0.200 | 0.019 | 1.2601e-06 | 4.9140e-06 | 3.90 | 1.2659e-06 |
| 0.350 | 0.172 | 1.0688e-06 | 4.0840e-06 | 3.82 | 1.0541e-06 |
| 0.500 | 0.485 | 6.6865e-07 | 2.5107e-06 | 3.75 | 6.3922e-07 |
| 0.700 | 0.880 | 1.5096e-07 | 5.5529e-07 | 3.68 | 1.5113e-07 |

**Prediction 1 confirmed.** With kappa on the lattice, L1 and Box have the same
error at the same degenerate fraction — agreeing to within 1-4% across a 46x
range of MSE. The soft-threshold has no intrinsic precision penalty over a
projection. The apparent penalty was entirely parameter quantization.

**Prediction 2 confirmed.** Measured off/on ratio 3.68-3.90 against a predicted
4.00. Since MSE ~ 2^(-2F), a 4x MSE penalty is exactly **one bit** of
wordlength.

### B.2 Full ADMM loop (kappa_nom = 0.35, target NMSE 1e-4)

| configuration | F* |
|---|---|
| L1, kappa on-lattice | **7** |
| L1, kappa off-lattice | 8 |
| Box, on-lattice | 6 |

**Prediction 3 confirmed.** Lattice alignment saves exactly one bit on the L1
lane, through the full closed loop, matching the operator-level prediction.

### B.3 The design rule

> Snap every operator constant (thresholds, projection bounds, scaling
> coefficients) onto the quantization lattice of the lane that consumes it.
> Off-lattice constants inject a bias on every element the operator does not
> annihilate, costing one full bit of datapath width for nothing.

Zero hardware cost, applied at elaboration. `reconfigurable_prox.v` already
re-derives constants with `q_narrow_const()`; the rule is to choose the Q2.16
source values so that derivation is exact. It also constrains the alpha scaling
of Lemma 1 to powers of two.

### B.4 Open discrepancy — do not paper over this

On-lattice L1 still needs 7 bits against Box's 6 in the closed loop, despite
identical operator-level error at matched d. The likely cause is the NMSE
metric: soft-thresholding shrinks ||z||, so the same absolute error normalises
to a larger relative error. That would make the residual gap a metric artifact
rather than a real precision difference — consistent with M5, where the
ordering flipped between NMSE and absolute error.

**Next check:** rerun B.2 with an absolute-error criterion. If the gap closes,
say so plainly in the paper and report both metrics. If it does not, there is a
loop-level mechanism the operator-level theory does not capture, and Theorem 2
needs a term for it.

---

## APPENDIX C — B.4 resolved, and the derived widths

### C.1 The metric artifact (`model/metric_check.py`)

mean ||z*||: L1 = 0.970, Box = 1.601. Soft-thresholding shrinks the solution by
1.65x, inflating L1's NMSE by 2.7x (~0.7 bit) relative to Box for the same
absolute error.

| target | L1 on-latt | L1 off-latt | Box | | target | L1 on-latt | L1 off-latt | Box |
|---|---|---|---|---|---|---|---|---|
| NMSE 1e-3 | 6 | 7 | 4 | | absMSE 1e-4 | 6 | 7 | 5 |
| NMSE 1e-4 | 7 | 8 | 6 | | absMSE 1e-5 | 7 | 8 | **7** |
| NMSE 1e-5 | 9 | 10 | 8 | | absMSE 1e-6 | 9 | 10 | 8 |

The L1-vs-Box gap narrows from 1-2 bits (NMSE) to 0-1 bits (absolute), and
closes entirely at absMSE 1e-5. The residual is within the +/-1 bit resolution
of the measurement. **Verdict: largely a metric artifact.** Declare the metric
in the paper and report both.

The lattice penalty is **exactly 1 bit under both metrics at every target** —
metric-independent, and therefore the most robust result we have.

### C.2 Derived lane widths (`model/derive_widths.py`)

Operating parameters kappa=0.10a, box=+/-1.00a, gamma=0.667, all lattice-snapped.
Degenerate fractions: d_L1 = 0.000, **d_Box = 0.494**, d_L2 = 0.000.

| target | L1 | Box | L2 |
|---|---|---|---|
| NMSE 1e-3 | 5 | 5 | 6 |
| NMSE 1e-4 | 7 | 6 | 7 |
| NMSE 1e-5 | 9 | 8 | 9 |

Box is consistently 1 bit cheaper, and Theorem 1 explains exactly why: d_Box =
0.494 means half of Box's error is annihilated, while L1 and L2 annihilate
nothing. (1-d) = 0.506 is a factor of ~2 in MSE, which is half a bit; the
measured 1 bit is that plus L2's coefficient term. The ordering is now derived
from a measured quantity, not asserted.

**Recommended widths, NMSE 1e-4 plus 1 bit design margin:**

| lane | F | total |
|---|---|---|
| L1 (sparse channel estimation) | 8 | **Q2.8, 10 bits** |
| Box (detection / precoding) | 7 | **Q2.7, 9 bits** |
| L2 (interference mitigation) | 8 | **Q2.8, 10 bits** |

### C.3 This changes the claim again — read carefully

Manuscript widths: 18 / 10 / 9. Derived widths: **10 / 9 / 10.**

Two consequences, and the second is uncomfortable:

1. The whole proximal array is over-provisioned by ~8 bits. Dropping 18 -> 10
   uniformly cuts multiplier area by (324-100)/324 = **69%** under the W^2 cost
   model. That is far larger than anything the asymmetry buys.
2. The asymmetric spread is **one bit, on one lane**. At this operating point
   the asymmetry is nearly worthless next to the uniform narrowing.

So the paper's headline cannot be asymmetry. It has to be: *an analytic error
model that derives the widths directly, with no search* — of which the
asymmetry is one modest consequence, sized by d.

The saving grace is that Theorem 2 now tells you **when** asymmetry is worth
having: it scales with the spread in degenerate fractions. Here d_Box - d_L1 =
0.494, worth 1 bit. In a regime with d_Box ~ 0.9 it would be worth 2-3 bits.
That is a defensible, quantitative statement, and it is more useful than a
fixed ordering.

### C.4 Caveat that must be closed before publishing these widths

Every F* above was measured with the **main datapath held at Q2.16** while one
lane varied. That isolates the lane, which is correct methodology, but it does
not license setting the main path to 10 bits. Narrowing the main path and the
lanes together compounds their errors. **A separate main-datapath sweep is
required** before the array width is changed.

### C.5 Synthesis matrix (`syn/run_ooc.tcl`, updated)

Four builds, fabric arithmetic throughout, separating the two effects the
earlier two-way sweep conflated:

| tag | F_L1 / F_Box / F_L2 | isolates |
|---|---|---|
| uniform18 | 16/16/16 | manuscript baseline |
| uniform10 | 8/8/8 | effect A: narrowing at all |
| asym_derived | 8/7/8 | effect B: asymmetry, derived widths |
| asym_manuscript | 16/8/7 | the manuscript's claimed configuration |

uniform18 -> uniform10 measures A. uniform10 -> asym_derived measures B.
If B is small next to A, that is the result and it gets reported as such.

---

## APPENDIX D — Main datapath sweep, and an invalidated synthesis run

### D.1 The result (`model/main_sweep.py`)

Full datapath parameterised: M, q, accumulator, x, v, z, u and residuals all
scale with F_M. Minimum F_M meeting each NMSE target:

| target | lanes pinned 8/7/8 | lanes tied to F_M |
|---|---|---|
| 1e-3 | L1=8 Box=7 L2=7 | L1=8 Box=7 L2=7 |
| 1e-4 | L1=9 Box=9 L2=9 | L1=9 Box=9 L2=9 |
| 1e-5 | **unreachable** | L1=11 Box=10 L2=10 |

Two conclusions:

1. At 1e-4 the columns are identical. Narrow lanes buy **zero** accuracy once
   the main path is sized. Combined with the +192 LUT cost measured earlier,
   asymmetric allocation is strictly dominated.
2. At 1e-5 the pinned configuration cannot reach the target at any F_M. Lanes
   narrower than the main path impose a hard error floor. Asymmetry caps
   achievable accuracy.

**Design point: fully uniform Q2.9 (11 bits) at NMSE 1e-4.** The main datapath
dominates the error budget; everything else was downstream of one number that
had never been measured.

### D.2 Bit-exact regression extended (`model/gen_vectors_fm.py`)

| F_MAIN | L1 | Box | L2 | |
|---|---|---|---|---|
| 16 | OK | OK | OK | PASS |
| 12 | OK | OK | OK | PASS |
| 10 | OK | OK | OK | PASS |
| 9 | OK | OK | OK | PASS |

RTL and golden model agree element-wise at every width. Iteration count falls
with precision (L2: 22 → 12 from F=16 to F=9) because the convergence test is
against a fixed epsilon, which a coarser lattice reaches sooner. Worth a
sentence in the paper — it is a real effect, not a bug.

### D.3 INVALIDATED: main10_uniform / main9_uniform / main9_asym

The first synthesis run at F_MAIN != 16 is void. `q_narrow_const` narrowed the
lane constants by (F_MAIN - F_lane) rather than (16 - F_lane), but the *_Q16
parameters are specified in Q2.16 regardless of F_MAIN. At F_MAIN=9 the shift
is zero and the raw Q2.16 constants land in 11-bit lanes:

| constant | derived | lane limit |
|---|---|---|
| KAPPA | 6554 | 1023 |
| BOX_HI | 32768 | 511 |
| GAMMA | 43691 | 1023 |

All three saturate to garbage identically in both builds, which is why
main9_uniform and main9_asym came back byte-identical in all twelve reported
columns including WNS. **Identical rows across different generics are the tell;
always check for them.**

Fixed by narrowing from a `SPEC_FRAC = 16` localparam. The F_MAIN=16 regression
is unaffected and still passes.

Rows uniform18 / uniform10 / asym_derived are unaffected (F_MAIN=16 throughout)
and remain valid.
