# Related work — Li et al., FAM (TRETS 2023)

Carol Jingyi Li, Xiangwei Li, Binglei Lou, Craig T. Jin, David Boland,
Philip H. W. Leong. "Fixed-point FPGA Implementation of the FFT Accumulation
Method for Real-time Cyclostationary Analysis." *ACM TRETS* 16(3), Art. 41,
June 2023. doi:10.1145/3567429

Read in full. This is the closest prior work and it is closer than expected.

---

## 1. What they actually did

- **Analytical SQNR model** for fixed-point FAM, built on the classical
  Oppenheim/Widrow statistical quantization model: additive noise, uniform on
  [−2^−F−1, 2^−F−1), variance (2^−F)²/12, propagated block by block with gains.
- Closed form: σ² = Σ_# W_# 2^(−2F_#) — a sum of products over the four blocks
  (window, FFT1, conjugate multiply, FFT2).
- **Two wordlength strategies compared:** FAM_M1 (uniform across the datapath)
  and FAM_M2 (mixed precision — grow width per addition, rescale).
- **Analytic bit allocation without search.** They minimise σ² by equalising
  each block's contribution, giving e.g. F−13 / F−8 / F−3 / F. Table 4
  validates this against an *exhaustive search* and reports that the analytic
  formula reaches similar allocations.
- Model matches bit-exact simulation to **within 1 dB**.
- HLS implementation on ZCU111 RFSoC, measured board power, throughput,
  GOPS, energy, comparison against GPU and other FPGA work.
- ACM artifact badges: Evaluated–Functional, Available, Results Reproduced.
  Open-source repository.

## 2. What this costs us

Three of the framings from earlier in this project do not survive contact with
this paper.

**"Analytic derivation instead of simulation search" is not novel.**
Li et al. do exactly that, and validate it against exhaustive search.
Constantinides et al. (2003) do it for linear DSP. This can no longer be the
headline. It must be reframed as *extending* analytic derivation to a case the
existing models cannot handle.

**The DSP-threshold observation is prior art.** Their Fig. 14(a) shows FAM_M1
DSP utilisation **doubling when wordlength goes 19 → 20 bits**, because the
DSP48E2 holds a 27×18 multiplier and 1 sign + 18 fraction bits = 19. They state
plainly that "wordlengths up to 18-bits are supported by the embedded DSP
blocks, and additional bits can be implemented using the programmable logic,"
and they deliberately pick 16 and 24 bits to sit either side of that threshold.
Cite this. Do not claim it.

**They already exploit noise-free operations.** Two of them:
- twiddle factors in {1, −1, j, −j} produce zero multiplication error, so the
  first two DIT stages are subtracted out of the noise expression (Eq. 20);
- the down-conversion factor takes only {i, −i, 1, −1} and injects no error.

A reviewer who knows this paper will ask how our annihilation result differs.
We need the answer ready, and it is a good one (§3).

## 3. What still differentiates us

**(a) Their operators are all linear; ours are not.** Windowing, FFT butterflies
and complex multiplication are linear maps. The Oppenheim/Widrow model is built
for exactly that case and has no mechanism for an operator that is *flat over a
region of its input domain*. Our measured result is that for non-smooth
proximal operators the classical model **overestimates error by 3–4× on
average, and by 900× at d = 0.999**. No linear noise model contains a (1−d)
term because in a linear system there is nothing to annihilate.

**(b) Their zero-error operations are structural; ours are data-dependent.**
Multiplying by ±1 or ±j is exact by construction, known at design time,
independent of the signal. Our degenerate fraction d depends on the input
distribution and the operator parameter, and must be estimated from the problem
rather than read off the architecture. That is a different kind of claim and it
is what makes the ordering regime-dependent.

**(c) Feed-forward versus fixed-point iteration.** FAM is a pipeline: error
propagates once, block to block, and the SQNR expression is a single pass. ADMM
is a closed loop — error re-enters the datapath every iteration, and the
relevant question is the radius of the converged neighbourhood, not the output
noise of one pass. This needs inexact-ADMM machinery (Eckstein & Bertsekas)
that has no analogue in their analysis.

**(d) The lattice rule.** They do not consider quantization of the *operator
constants* as a separate error source. Our measured result — an off-lattice
constant costs exactly one bit, metric-independently — has no counterpart here.

**(e) Profitability condition.** They *observe* the DSP threshold and design
around it. We give a closed-form condition including the cast overhead term,
and it predicts the **downward** direction they never test: narrowing *below*
the macro width converts a free hard multiplier into a paid fabric one and is
net-negative. Their Fig. 14 only explores upward crossings.

## 4. A finding of theirs that supports our negative result

Table 4, FAM_M2, DeepSig, F_sum = 72 bits:

| allocation | SQNR |
|---|---|
| non-uniform 17 / 17 / 19 / 19 | 84.29 dB |
| uniform 18 / 18 / 18 / 18 | 82.85 dB |

**1.44 dB.** Once the underlying precision scheme is well designed (M2),
non-uniform allocation buys almost nothing over uniform at equal total bits.
Their FAM_M1 gap is large (46.04 vs 15.87 dB) only because M1's uniform
baseline is itself a poor design — it right-shifts at every addition.

This is the same shape as our result: **against a properly sized uniform
baseline, per-block wordlength specialisation is marginal.** We should cite
this explicitly. It converts our most awkward finding from an outlier into a
second, independent observation of the same effect in a different algorithm.

## 5. Revised claim set

| claim | status |
|---|---|
| Degenerate-set error model for non-smooth proximal operators | **Primary. Novel.** |
| Error analysis through a fixed-point iteration, not a feed-forward pipeline | **Secondary. Novel.** |
| Lattice rule for operator constants | **Secondary. Novel.** |
| Profitability condition with cast overhead; the downward/negative direction | **Secondary. Formalises + extends prior observation.** |
| Analytic derivation instead of search | **Drop as a headline.** Cite Li et al. and Constantinides. |
| DSP operand-width threshold | **Drop as a claim.** Cite Li et al. Fig. 14. |

Revised one-sentence positioning:

> Classical quantization models assume every element of a datapath contributes
> q²/12 of noise. That assumption is exact for the linear pipelines those models
> were built for, and wrong by 3–4× for the non-smooth proximal operators at the
> centre of ADMM accelerators. We give the corrected model, validate it to
> within 1%, and compose it with a fabric cost model into a closed-form test for
> when per-operator wordlength specialisation pays.

## 6. What this paper sets as the bar

They are the standard our results section will be measured against:

| they report | we currently have |
|---|---|
| SQNR model vs bit-exact sim, within 1 dB | model vs bit-exact, within 1% ✓ (better, simpler system) |
| Measured board power (AC meter) | vectorless estimate only ✗ |
| Throughput MS/s, GOPS, energy mJ | none ✗ |
| Comparison vs GPU and prior FPGA | none ✗ |
| Open source + ACM artifact badges | repo is well positioned ✓ |

Items 2–4 are not optional at this venue. They are in the sprint.

## 7. Tactical notes

- FAM is TRETS. Leong and Boland (Sydney) are plausible reviewers for anything
  we send to TRETS/FCCM/FPL in this area. **Write the related-work section for
  them.** Get the distinction in §3 right and stated early.
- Their open-source repo is a useful template for artifact packaging.
- Their model is validated on three input signals (sine, square, DeepSig
  RADIOML). Our generalisation sweep should match or exceed that breadth —
  it is the obvious "you only tested one case" attack and they pre-empted it.

---

# Citation pass, 2026-09-04

Forward-citation sweep on Constantinides and on fixed-point ADMM. Findings
below are ordered by threat to novelty. **This changes the framing.**

## §A. THE PRIMARY PRIOR ART — Jerez, Goulart, Richter, Constantinides, Kerrigan, Morari

*"Embedded Online Optimization for Model Predictive Control at Megahertz
Rates"*, arXiv:1303.1090, IEEE TAC. **This is the paper the framing must be
written against.** It is a Constantinides paper, on fixed-point ADMM, on FPGA,
with explicit wordlength selection. It was not in RELATED_WORK before.

What it already does:
- Fixed-point ADMM (and fast gradient) on FPGA, parameterised VHDL generators.
- A round-off error propagation analysis for ADMM: two-step error recurrence
  (their eq. 17), Schur stability via Lyapunov (Lemma 2), and a converging
  upper bound on accumulated error (Prop. 2, eq. 20).
- States the bound "can be used to determine a priori the minimum number of
  bits required to achieve a given solution accuracy specification, resulting
  in minimal resource usage." That is wordlength selection for ADMM.
- Empirical bits-vs-iterations table (their Table II): b=18 fraction bits and
  ~40 iterations is where ADMM stops improving; notes ADMM is "more vulnerable
  to reduced precision" than the fast gradient method.

**The opening this leaves us — and it is a good one.** In deriving their
bound they write that for the projection step "no arithmetic error is
introduced... the error can only be reduced by multiplication with a diagonal
matrix diag(pi_eps,i), with pi_eps,i componentwise in the interval [0,1]."

That diagonal matrix IS our degenerate-set annihilation. They identify the
mechanism and then **discard it** — they set diag(pi)=I ("in the absence of
the projection operation... these errors remain bounded") to obtain a
conservative bound.

So our contribution states precisely: prior art identified that the proximal
step scales error by a diagonal matrix in [0,1]^n but dropped the factor to
keep the bound conservative. We QUANTIFY it as (1-d) with d the measured
degenerate fraction, show it is the dominant term (3-4x typically, 900x at
d=0.999), and validate predictively rather than as a bound (model/measured
0.99-1.00) against routed silicon.

Other distinctions, all defensible:
- Theirs is an upper BOUND; ours is a PREDICTIVE model. Different object.
- They assume "all variables and problem data are represented using the same
  number of fraction bits b" — no per-lane or mixed precision. Our per-operator
  lane widths are outside their scope.
- Their ADMM overflow analysis FAILS by their own admission: "we do not know
  of any general method to upper bound the Lagrange multiplier iterates."
  We use saturating arithmetic and measure. Worth stating plainly.
- No power measurement; they report multiplier counts and estimated sample rates.

**Action: this paper must be cited in the first three sentences of §II.**

## §B. The Heriot-Watt cluster (Hamadouche, Wu, Wallace, Mota) — second threat

A sustained line on approximate/inexact ADMM under reduced precision:
- arXiv:2306.16964, *Improved Convergence Bounds for Operator Splitting
  Algorithms with Rare Extreme Errors* — probabilistic bounds for approximate
  proximal ADMM via Bernstein concentration, explicitly motivated by
  "mixed-precision fixed-point arithmetic" on FPGAs.
- arXiv:2210.02094, *Probabilistic Verification of Approximate Algorithms with
  Unstructured Errors: Fully Inexact Generalized ADMM*.
- arXiv:2203.02204, *Sharper Bounds for Proximal Gradient Algorithms with Errors*.
- arXiv:2306.16935, *A Low-Power Hardware-Friendly Optimisation Algorithm...* —
  ADMM and DFGPGD on a ZCU106, W=24 (16 int / 8 frac), with a dynamic
  power/error-rate trade-off metric. **They already do power-vs-error on real
  hardware.** Our measured-SAIF discipline is the differentiator, not the idea.
- Wu, Wallace, Mota, *Efficient Reconfigurable Mixed Precision l1 Solver for
  Compressive Depth Reconstruction*, J. Signal Process. Syst. 2022 — mixed
  precision ADMM and PGD on FPGA, reporting up to 67% LUT and 80% DSP
  reduction. **NOT FULLY READ — paywalled, see §D.** This is the closest
  numerical claim to our headline and MUST be read before drafting.

Key distinction to hold: their error models assume the proximal error is
zero-mean, bounded, conditionally-mean-independent additive noise (their
Model 2). Our central finding is that this assumption is wrong in a specific,
quantifiable way — the prox annihilates a fraction d of the error rather than
passing it through. That is a refinement of their model, and worth framing as
such rather than as a competing result.

## §C. Lower-threat neighbours

- Li et al., TRETS 2023 (10.1145/3567429), already in RELATED_WORK. Confirmed:
  analytical SQNR model for FAM/SCD, two wordlength strategies (uniform
  FAM_M1 vs mixed FAM_M2). Different algorithm; the methodological bar
  (validate across signals, report measured power) is what we inherit.
- Dang, Ling, Maciejowski, *Embedded ADMM-based QP solver for MPC with
  polytopic constraints* — fixed-point ADMM on FPGA, step-size heuristics.
  No error model.
- FPGA QP/ADMM path-planning accelerators (ADMM + PCG) — throughput work,
  no precision analysis.
- cuOSQP / GPU ADMM — floating point, not relevant beyond citation hygiene.

## §D. WHAT I COULD NOT ACCESS — must be checked before drafting

1. **Wu, Wallace & Mota, J. Signal Process. Syst. 2022** (Springer paywall).
   Abstract only. Closest numerical claim to our headline (67% LUT / 80% DSP).
   **Highest priority to obtain.**
2. **Li et al., TRETS 2023** — read via search excerpts only, not the full
   text. Our characterisation of it should be re-verified against the PDF.
3. **Hamadouche arXiv:2210.02094 and 2203.02204** — snippets only.
4. **FCCM / FPL / TRETS proceedings 2024-2026** — could not enumerate
   systematically without IEEE Xplore and ACM DL access. Everything found was
   via secondary citation. **A manual Xplore/DL sweep is still owed** — this
   pass does NOT discharge that TODO item, it only front-loads the highest-
   threat hits.
5. Google Scholar forward-citation list on Constantinides 2003 itself —
   Scholar is not machine-accessible from here. The Jerez paper was reached
   by subject search, not by citation traversal, so the traversal is still
   owed and may surface more.

## §E. Consequences for the paper

1. The novelty claim must narrow to: *quantifying* the degenerate-set
   annihilation factor that Jerez et al. identified and discarded, and
   validating it predictively against routed silicon.
2. "First error model for fixed-point ADMM" is NOT available. Jerez et al.
   (2013) have one. Do not write it.
3. Per-lane/mixed-precision framing is safer ground than "fixed-point ADMM
   error analysis", but Wu et al. 2022 already do mixed-precision ADMM, so
   read that first.
4. Our measurement discipline (SAIF power, swept Fmax, bit-exact gate-level
   validation) appears stronger than most of this literature, several of which
   report vectorless or estimated numbers. That is a defensible secondary
   contribution and should be stated.

---

# Wu et al. 2022 — read in full (2026-09-04). §B upgraded.

Wu, Wallace, Mota, Aßmann, Stewart, *Efficient Reconfigurable Mixed Precision
l1 Solver for Compressive Depth Reconstruction*, J. Signal Process. Syst.
94:1083-1099, 2022. DOI 10.1007/s11265-022-01766-3. Open Access (CC BY).
Flagged in §D as the closest numerical claim to our headline. Now read.

**Verdict: much less threatening than the abstract suggested, and it supplies
independent support for our negative result.**

## What they actually do
Mixed-precision ADMM and PGD for lasso (compressive LiDAR depth), HLS on a
Zynq UltraScale+ ZCU106, Vivado 2019.1. Precision varies ACROSS ITERATIONS
(low early, high late), k_max = 5. Reported: up to 67% LUT / 80% DSP / 60%
dynamic power for ADMM vs FP32.

## Three separations, all in our favour

1. **Their power is ESTIMATED, not measured.** Sect. 4.2: resources come from
   place-and-route but "the power is estimated using the Xilinx Power
   Estimator (XPE)". XPE is a spreadsheet tool. Every power figure in their
   Table 1, including the 60% headline, is the same class of estimate we
   spent 2026-09-04 replacing. Our SAIF-measured numbers at Confidence High
   are methodologically stronger than the closest competing work. This
   promotes measurement discipline from housekeeping to a stated contribution.

2. **They have no error model.** Bit widths come from exhaustive search
   against a static proxy: quantise the PRECOMPUTED constants g and H, measure
   eps by their Eq. (12)/(13), take the smallest width with eps <= omega =
   5e-3. That is a quantisation check on stored coefficients. Nothing in it
   predicts the solver's output error, and it does not propagate through
   iterations. Our predictive model (0.99-1.00 model/measured) occupies ground
   they left empty.

3. **Orthogonal precision axis.** Theirs is TEMPORAL (per iteration); ours is
   SPATIAL (per operator lane). The lane axis is unexplored by them.

## Independent corroboration of OUR negative result

Their own Table 1, ADMM fixed-point rows:

| config | LUT | DSP | dyn power (W) |
|---|---|---|---|
| consistent FXP24 | 6775 | 30 | 0.316 |
| mixed FXP20->24 | **6807** | 21 | 0.307 |

Non-uniform precision COSTS 32 LUTs versus uniform at the top width. Their
abstract claims "over 10% saving in hardware resources... compared to relative
consistently reduced precision solutions", but that claim is carried by the
PGD and floating-point rows; the ADMM fixed-point row shows a LUT INCREASE.

This is a second, independent data point for our finding that per-operator
asymmetry costs area. Cite it. They did not remark on it.

## MUST PRE-EMPT: the headline numbers are not comparable

They report 67% LUT / 60% power; we report 46.6% LUT / 36% dynamic power. A
reviewer will read ours as weaker. The baselines differ:

- **Theirs: FP32 floating-point -> fixed point.** Most of the win is the
  float-to-fixed conversion itself.
- **Ours: Q2.16 fixed -> Q2.9 fixed.** Narrowing WITHIN fixed point, with the
  float-to-fixed win already banked in the baseline.

State this explicitly in Sect. II. Also note their part is an UltraScale+
ZCU106 at ~400-470 MHz; ours is an Artix-7 35T. Absolute figures are not
comparable across parts either.

## Li et al. TRETS 2023 — full citation resolved

Carol Jingyi Li, Xiangwei Li, Binglei Lou, Craig T. Jin, David Boland,
Philip H. W. Leong. *Fixed-point FPGA Implementation of the FFT Accumulation
Method for Real-time Cyclostationary Analysis.* ACM TRETS 16(3), Article 41,
1-28, June 2023. DOI 10.1145/3567429.

Free routes (no paywall needed): artifact repo github.com/Jingyi-li/FAM_Synthesis,
and Jingyi Li's 2025 University of Sydney thesis, open access at
ses.library.usyd.edu.au, covering the same material at length.

**Their accuracy bar is TIGHTER than ours.** They report calculated SQNR
agreeing with bit-exact simulation to under 1 dB, i.e. ~0.17 bits, across
wordlengths 14-26. Our criterion is 0.5 bits ~ 3 dB. Our L2 term (0.031 bits)
clears their bar; Box (0.234) and L1 (0.340) do not. The objects differ —
their SQNR for a fixed pipeline vs our loop gain across a conditioning sweep —
but the 0.5-bit criterion must be JUSTIFIED in the paper, not asserted, or a
reviewer from this community will hold their bar against us.


---

# P4 DISCHARGED — citation traversal complete, 2026-09-06

Method: `tools/lit_sweep.py` (dblp venue enumeration + OpenAlex forward-citation
traversal). Reproducible from the repo, per the repo rule. Raw output in
`results/lit_sweep.txt`, `results/cites.txt`, `results/cites_kinsman.txt`.

## VERDICT: no collision. The novelty claim holds in its narrowed form.

## The decisive finding — Kinsman & Nicolici's lineage is a dead end

*Automated Range and Precision Bit-Width Allocation for Iterative Computations*,
TCAD 30(9) 2011, DOI 10.1109/TCAD.2011.2152840, OpenAlex W2131433010.
The closest published work to this project: SMT-based bit-width allocation,
case study on CONJUGATE GRADIENT, descends from Constantinides 2003.

**It has 16 citations in 15 years, and NONE extend it to iterative optimisation
solvers.** The 11 that pass the relevance filter go to range/overflow analysis:
matrix factorization (JSPS 2018), EKF-SLAM systolic arrays (JSPS 2017), OS-ELM
(IEICE 2021), eigenvalue decomposition (DASIP 2017), fixed-point LTI (2020),
divide-and-conquer bit-width (TC 2015).

**The field went toward RANGE analysis (integer bits, overflow-freedom), not
toward precision error models for NONLINEAR operators.** That is the gap.

## Three quotes from the prior art that define our contribution

1. **Jerez, Goulart, Richter, Constantinides, Kerrigan & Morari** (arXiv:1303.1090)
   observe the proximal step scales error by "a diagonal matrix with entries
   componentwise in the interval [0,1]" -- then DISCARD it for a conservative
   bound.
2. **Kinsman & Nicolici** (TCAD 2011) state their constraints "assume no
   correlation between quantization error and value, when in reality
   correlation may exist. **If the nature of the correlation is known, it can
   be captured into constraints.**"
3. **Ha & Sentieys** (DATE 2020 and again DATE 2023): "Existing techniques are
   limited to modeling noise power metrics of **Linear and Time-Invariant
   (LTI) systems** (with some extensions)."

Two papers named the gap; the third confirms it was still open in 2023.
The proximal operator is not LTI. (1-d) is that characterisation.

## THE THREAT TO ANSWER BEFORE SUBMISSION

Kinsman & Nicolici Sect. V-D-4 is a direct attack on empirically-validated
bit-widths. Against a CG implementation validated by 50-point Monte Carlo,
they construct an adversarial b equally weighted across eigenvectors of K:
normalised error 0.083 after 25 iterations, **~35 standard deviations beyond
the simulated worst case, ~40 from the mean**. Over 100 iterations needed to
reach the error simulation predicted at 25. They further show DOUBLE PRECISION
is not immune (computed residual 1.09e-1 vs true residual 7.96).

Our model is validated over RANDOM conditioning sweeps. A reviewer holding
this paper will ask about the adversarial corner. **We must either state a
worst-case result or scope the claim explicitly: the model is predictive
in-distribution, NOT a robustness bound.** Do not let this arrive unanswered.

## Their numbers, for contrast (use carefully)

Kinsman & Nicolici's robust CG bit-widths run "into the hundreds of bits";
after heavy input-space restriction, "nearly single-precision floating point in
some cases, and between single and double precision for others". We reach 9
bits, bit-exact on routed silicon. This is NOT a like-for-like comparison --
theirs is a robustness guarantee, ours is a predictive model -- and must be
presented as a difference in OBJECT, not a claim of superiority.

## Supporting allies (cite, do not fear)

- **Lopez, Carreras & Nieto-Taladriz**, TCAD 2007: the additive linear noise
  model embeds "two wrong assumptions" in feedback loops; AA bounds converge to
  a constant E_inf "which does not depend on the values of the signals but only
  on the quantization operations... due to the additive nature of the linear
  noise model." Same disease we diagnose, applied to LTI ranges.
- **Naud, Menard, Caffarena & Sentieys**, TCSII 2012: NOT our correlation
  (theirs is between two quantisations of one datum). But shows classical
  independence assumptions cost up to 84% estimation error and 10-18% energy
  overhead. Supporting evidence that the classical model fails.

## Neighbours, low threat

- Ha & Sentieys DATE 2023, Ha/Yuki/Sentieys DATE 2020: SEARCH methods
  (Bayesian/TPE, noise budgeting), no error model. Cite for currency.
- Li et al. FPL 2024, Wu et al. FPGA 2026: DSP48E2 packing on UltraScale. We
  are Artix-7 with USE_DSP_L2=0. Cite one when disclaiming the operand-width
  threshold.

## Residual gap, stated honestly

5 of Kinsman's 16 citing works were dropped as no-keyword and not inspected.
Small, but not zero. Everything else has been enumerated or read.
