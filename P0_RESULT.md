# P0 result — loop-gain model closed, mechanism claim withdrawn

> **RETRACTION (2026-09-20).** P0.1 and P0.2b below did not survive a held-out
> test (`model/margin.py`). Leave-one-condition-out on the SAME seeds hid that
> the L1 ensemble mean is dominated by one instance (68% of the ensemble MSE)
> and moves 0.59 bits between seed sets, more than the 0.34-bit error claimed.
> Held out: L1 1.38 bits, Box 0.73 bits, L2 0.046 bits. Only the L2 model
> generalises. The churn refutation (P0.2a) stands. See THEOREM_LOCK.md.
> The text below is kept as the record of what was believed and why.

Date: 2026-09-04. Scripts: `model/loop_gain_l1.py`, `model/box_form.py`.
Outputs: `results/loop_gain_l1.json`, `results/box_form.json`.

---

## P0.1 — the L1 active-set term closes

Adding `d` as a second regressor to the loop-gain fit:

| operator | baseline LOO | with `d` | criterion 0.5 bits |
|---|---|---|---|
| L1  | 0.928 | **0.340** | pass |
| Box | 0.513 | **0.234** | pass |
| L2  | 0.108 | n/a (d ≡ 0) | pass |

16 conditioning points, 20 trials each, `d` averaged over trials (a bug in
`loop_gain.py` recorded only the last trial; patched). Scored by
leave-one-out, not in-sample — with only 16 points a second regressor
improves in-sample fit almost automatically.

**Confound tested and rejected.** `d` correlates with conditioning at
corr² = 0.94, so the obvious objection is that it merely proxies conditioning
where `log(1/(1-||M||₂))` saturates. It does not: `log(cond)` as the second
regressor gives LOO 1.237 for L1, *worse than the baseline*, and adding it
alongside `d` contributes nothing. `d` carries information conditioning does
not.

## P0.2a — the churn mechanism is REFUTED

The two operators take `d` with opposite signs (+20.6 L1, −20.4 Box). The
proposed mechanism was that L1's degenerate set churns (entries flipping in
and out of the soft-threshold zero set) while Box's freezes (entries pinned
to the clip bound), making the same statistic destabilising in one and
stabilising in the other.

Churn was measured directly: `c = mean_t[fraction of coordinates whose
degenerate-set membership changes between iterations t and t+1]`.

| prediction | result |
|---|---|
| P1: L1 churns, Box frozen | **FAIL** — L1 mean 0.0011, Box mean 0.0028. Box churns *more*. Both are ~0.1–0.3%, i.e. both essentially frozen. |
| P2: churn unifies the sign | pass — positive coefficient for both |
| P3: churn fits at least as well as `d` | **FAIL** — L1 LOO 0.781 with churn vs 0.340 with `d` |

Two of three predictions fail. There is no churn/freeze distinction to build
a mechanism on.

**What actually sets the sign:**

| | d at cond=1 | d at cond=300 | corr(d, log cond) |
|---|---|---|---|
| L1  | 0.000 | 0.596 | +0.969 |
| Box | 0.518 | 0.172 | −0.975 |

`G` rises with conditioning for both operators. `d` rises with conditioning
for L1 and falls for Box, so the coefficient sign simply follows `d`'s
monotonicity. The sign flip is a property of how the degenerate fraction
moves with conditioning in each operator — not evidence of two mechanisms.

## P0.2b — Box functional form

Box prefers `d²` over `d`: LOO 0.178 vs 0.234. Paired comparison of LOO
absolute residuals gives t = 2.56 on 15 df, significant at 5%.

Caveat to carry: several candidate forms were tried before this one, so the
p-value is not corrected for selection. The effect is real but the exact
exponent should be presented as fitted, not derived.

**The two operators do not share a functional form.**

---

## What may be claimed

The loop-gain model is **empirical**, one fitted form per operator:

    log G = a·log(1/(1 - ||M||₂)) + b·R_op + c

    R_L1  = d
    R_Box = d²
    R_L2  = none (the resolvent term already suffices, LOO 0.031)

All three inside the 0.5-bit criterion under leave-one-out.

## What may NOT be claimed

- Any mechanism for the sign difference. Churn was the candidate and it failed.
- A unified functional form across operators. `d` vs `d²` is a significant
  difference.
- That `d` is merely a conditioning proxy — that was tested and rejected, so
  the term is doing real work even without a mechanism.

Consequence for the theorem set: the loop-gain relation is stated as a fitted
model with a per-operator term, validated by cross-validation, not as a
derived result. Theorem 1's `(1-d)` annihilation term is separate and remains
derived and validated (0.99 / 1.00, Appendix A).
