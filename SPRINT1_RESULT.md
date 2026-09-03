# Sprint 1 — generalisation result

`model/generalize.py`. 4 ensembles (Gaussian, ill-conditioned cond=50,
exponentially correlated, uniform) x 2 sizes (N=8, 16) x 3 operators = 24 cells,
25 systems each, all constants lattice-snapped, F=10.

## The test, and its failure

Hypothesis: MSE = K (C + A_op) q^2/12 with ONE global constant absorbing the
main-datapath contribution and the loop amplification.

| model | mean error | max error |
|---|---|---|
| Theorem 1 (with the (1-d) term) | 2.509 bits | 4.243 bits |
| classical Oppenheim/Widrow | 2.879 bits | 4.152 bits |

**FAIL** against the 0.5-bit criterion. Theorem 1 beats the classical model but
neither is close. The composition of the operator model with the loop —
Theorem 5 in THEORY_PLAN, flagged there as the most likely to fail — does not
hold with a constant loop gain.

## Why: the loop gain is not a constant

Dividing the operator term out, G = MSE / (A_op q^2/12):

| ensemble | N | G(L1) | G(Box) | G(L2) |
|---|---|---|---|---|
| gaussian | 8 | 79 | 83 | **8.6** |
| gaussian | 16 | 114 | 98 | **13.4** |
| ill-conditioned | 8 | **196,457** | 5,118 | **12.4** |
| ill-conditioned | 16 | 69,740 | 7,709 | **17.2** |
| correlated | 8 | 796 | 784 | **16.0** |
| correlated | 16 | 1,240 | 1,102 | **22.9** |
| uniform | 8 | 56 | 46 | **7.0** |
| uniform | 16 | 100 | 76 | **12.3** |

G spans **four orders of magnitude** for L1. A single constant was never going
to fit it.

## The finding this exposes

**G(L2) is 7-23 across every ensemble and both sizes. Nearly invariant.**
G(L1) and G(Box) range from 46 to 196,457.

The L2 lane is the only strict contraction (gamma = 0.667). Its contraction
does not reduce the *operator-level* error — Appendix A showed coefficient
quantization dominates there, and A_L2 is the largest of the three. But it
almost completely suppresses *loop-level* amplification, and does so
independently of problem conditioning.

**Contraction acts at the loop, not at the operator.** The original theory put
it at the operator and was wrong there. It is right one level up, and this is a
sharper statement than the one it replaces:

> A contractive proximal operator needs no fewer bits than a non-contractive
> one — its coefficient quantization sees to that. What it buys is immunity to
> loop-level error amplification, which is worth up to four orders of magnitude
> and is what actually determines the datapath width in an ill-conditioned
> problem.

## Theorem 2's premise, revisited

Ill-conditioned L1 has G = 196,457, two orders above Box on the same ensemble.
That gap is active-set instability: near-degenerate problems make the set of
zeroed components sensitive, so a perturbation changes which components survive
and the trajectory diverges.

We measured that effect at exactly zero in the well-conditioned Gaussian case
(STATUS M6), and concluded the original Theorem 2 mechanism was inoperative.
**It is operative — in the ill-conditioned regime only.** The original theorem
was not wrong, it was unscoped. That is a recoverable result and a better one,
because now we can say when it applies.

## Candidate predictors for G (next experiment)

| ensemble | cond(M) | \|\|M\|\|_2 | rho(I - rho M) |
|---|---|---|---|
| gaussian | 2.15 | 0.741 | 0.6524 |
| ill-conditioned | 2.90 | **0.999** | 0.6524 |
| correlated | **7.12** | 0.970 | **0.8604** |
| uniform | 2.17 | 0.752 | 0.6512 |

- Spectral radius of the ADMM map explains correlated vs gaussian: predicted
  gain ratio (0.35/0.14)^2 = 6.3 against a measured 10. Plausible.
- It does NOT explain ill-conditioned, which has the same spectral radius but
  1000x the gain. There \|\|M\|\|_2 -> 0.999 is the distinguishing quantity.
- So G likely needs both a spectral-radius term and a near-unity-norm term,
  plus an active-set-stability term for L1 specifically.

## Consequences for the paper

1. **Theorem 5 (composition) is demoted to discussion**, exactly as
   THEORY_PLAN pre-planned for this outcome. Do not force it.
2. **Theorems 1, 2 (operator error) stand** — validated to 1% at operator level
   in Appendices A and B, and untouched by this result.
3. **Theorems 3, 4 (cost, profitability) stand** — measured on silicon,
   independent of the loop.
4. **New result to add:** contraction operates at the loop level. Four orders
   of magnitude, measured across four ensembles and two problem sizes.
5. **Theorem 2 is rescoped** rather than dropped: active-set instability is real
   in ill-conditioned problems and absent in well-conditioned ones.

## Next

Model G. Sweep condition number continuously (rather than two discrete
ensembles), measure G against \|\|M\|\|_2 and the ADMM map spectral radius, and
test whether a two-term form predicts within 1 bit. This is now the critical
path — everything else in Sprint 1 (SAIF power, Fmax, throughput) is
measurement hygiene and can run in parallel.

---

# Sprint 1b — the loop gain is modelled (`model/loop_gain.py`)

Condition number swept continuously, 1 -> 300, N=8, F=10, 20 systems per point.

For a linear fixed-point iteration s <- Ts + e, steady-state error is set by the
resolvent ||(I-T)^-1||. ADMM with a linear prox IS such an iteration, and T is
exact:

    s = (z, u),   A = rho*M,   B = I - rho*M,   g = prox gain

    T = [[ g*A , g*B ], [ (1-g)*A , (1-g)*B ]]

## Measured

| cond | \|\|M\|\|_2 | resolvent (g=1) | resolvent (g=0.667) | G(L1) | G(Box) | G(L2) |
|---|---|---|---|---|---|---|
| 1 | 0.747 | 4.2 | 2.4 | 80 | 82 | 8.8 |
| 5 | 0.928 | 14.3 | 2.9 | 355 | 211 | 10.8 |
| 20 | 0.995 | 213 | 3.16 | 179,330 | 3,018 | 11.1 |
| 100 | 0.9998 | 5,297 | 3.18 | 487,408 | 4,080 | 11.1 |
| 300 | 1.0000 | 47,669 | 3.18 | 561,502 | 5,861 | 10.9 |

**The resolvent with g=1 diverges (4 -> 47,669) as \|\|M\|\|_2 -> 1. With
g = 0.667 it saturates at 3.18.** The contraction does not merely reduce the
gain — it *bounds* it, independently of conditioning. That is the mechanism.

## Fits (log-log, per operator)

| operator | predictor | slope | R^2 | mean error |
|---|---|---|---|---|
| L2 | resolvent | 0.96 | 0.825 | **0.031 bits** |
| Box | 1/(1 - \|\|M\|\|_2) | 0.51 | 0.863 | **0.399 bits** |
| L1 | 1/(1 - \|\|M\|\|_2) | 1.06 | 0.866 | 0.834 bits |

Against the 0.5-bit criterion: **L2 and Box pass, L1 fails.**

## Reading

- **L2**: G tracks the resolvent with slope ~1 and 0.03-bit error. Because a
  strict contraction caps the resolvent, G is bounded (7-12) across a 300x
  conditioning range. Clean, and it is the whole contraction story stated
  correctly.
- **Box**: exponent 0.5 rather than 1. Clipping is *stabilising*: measured d
  falls from 0.35 to 0.078 as conditioning worsens, and the clipped components
  are frozen, which damps the loop.
- **L1**: exponent ~1 and the largest residual. d *rises* from 0.00 to 0.70 as
  conditioning worsens — the active set is churning. Soft-thresholding is
  destabilising where clipping is stabilising, and a resolvent argument alone
  does not capture it. This is the active-set instability of Theorem 2, and it
  needs its own term.

## Statement for the paper

> The loop amplification of quantization noise in fixed-point ADMM is governed
> by the resolvent of the linearised iteration map, into which the proximal
> operator enters as a gain. A strict contraction bounds that resolvent
> independently of problem conditioning; a non-expansive operator does not, and
> the gain grows without bound as \|\|M\|\|_2 -> 1. Contraction therefore buys
> nothing at the operator level and up to five orders of magnitude at the loop
> level.

## Remaining gap

L1 at 0.834 bits. Needs an active-set-churn term — d itself is the obvious
candidate, since it moves monotonically with conditioning (0.00 -> 0.70).
Next experiment: add d as a second regressor for L1 and test.
