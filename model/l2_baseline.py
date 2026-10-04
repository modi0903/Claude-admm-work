"""
l2_baseline.py -- is the L2 loop-gain model better than a constant?

Reviewer objection (2026-10-04): across conditioning 1..300 the L2 loop gain
G only ranges 7.9..12.3 (loop_gain.txt), so the 0.046-bit held-out error of
the resolvent model might be no better than predicting one constant.

Same fit seeds, same disjoint held-out seeds, same ensemble statistic as
margin.py. Three predictors of log G per conditioning cell:
  resolvent  log G = a log R + c          (the published model, 2 params)
  constant   log G = mean over fit cells  (1 param)
  no loop    G = 1, i.e. operator error only, no loop amplification (0 params)
Reported in bits of wordlength, held-out mean |error| and per-instance p99.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from margin import collect, FIT_SEED, FIT_TRIALS, HELD_SEED, HELD_TRIALS

b = lambda v: v / (2 * np.log(2))


def main():
    fit = collect(FIT_SEED, FIT_TRIALS, 2)
    held = collect(HELD_SEED, HELD_TRIALS, 2)
    X = np.array([c["feat"] for c in fit]); y = np.array([c["arith"] for c in fit])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    const = float(y.mean())
    preds = {"resolvent": lambda f: float(np.dot(f, coef)),
             "constant": lambda f: const,
             "no loop (G=1)": lambda f: 0.0}
    out = {}
    hy = np.array([c["arith"] for c in held])
    print(f"L2 loop gain across held-out cells: G = {np.exp(hy.min()):.1f} .. {np.exp(hy.max()):.1f}"
          f"  ({b(hy.max() - hy.min()):.2f} bits of spread)\n")
    print(f"{'predictor':15s} {'params':>6s} {'held-out |err|':>15s} {'per-inst p99':>13s} {'max':>7s}")
    for name, p in preds.items():
        he = b(np.mean([abs(c["arith"] - p(c["feat"])) for c in held]))
        per = np.array([b(l - p(f)) for c in held for l, f in c["per"]])
        npar = {"resolvent": 2, "constant": 1, "no loop (G=1)": 0}[name]
        out[name] = dict(params=npar, heldout_err=float(he),
                         p99=float(np.quantile(per, 0.99)), max=float(per.max()))
        print(f"{name:15s} {npar:6d} {he:15.3f} {np.quantile(per, 0.99):+13.2f} {per.max():+7.2f}")
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "results", "l2_baseline.json"), "w"), indent=1)
    print("\nsaved -> results/l2_baseline.json")


if __name__ == "__main__":
    main()
