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
