"""
margin.py -- per-instance safety margin for the loop-gain model (TODO item 3).

The loop-gain model is fitted on 20-trial ENSEMBLE means at each conditioning
point, and the published errors (0.834 / 0.399 / 0.031 bits, and the LOO
figures 0.340 / 0.234) are ensemble-level. adversarial.py showed that per
instance it UNDER-predicts by up to +7.6 bits on random inputs -- but that is a
worst case over ~50 draws, which is not a margin anyone can quote.

This script produces the quotable number: a QUANTILE of the per-instance error
on HELD-OUT problems (seeds disjoint from the fit), with the model fitted
exactly as reported.

Error is SIGNED, in bits of wordlength:
    e = 0.5*log2(G_measured / G_predicted)
    e > 0  model under-predicts error -> a width chosen from it is too narrow
    e < 0  model over-predicts        -> conservative, wasted bits
A designer who adds ceil(p) bits to the model's W* is safe on a fraction q of
instances, where p is the q-quantile of e. That is the margin.

GEOMETRIC MEAN IS ILL-POSED FOR BOX. Some Box instances have EXACTLY zero
error (every coordinate clipped, fixed == float bit for bit): 16 of 720 here.
log(0) is undefined, so the geometric mean depends on how those instances are
treated -- dropping them vs. averaging features over them moved the Box held-out
error between 0.43 and 0.63 bits. The ARITHMETIC-mean result is the well-defined
one and is the one to quote. The geometric column is reported only to show that
a robust statistic does not rescue L1 either.

Model, as fitted in loop_gain_l1.py / box_form.py / loop_gain.py:
    L1 : log G = a*log(1/(1-||M||2)) + b*d   + c
    Box: log G = a*log(1/(1-||M||2)) + b*d^2 + c
    L2 : log G = a*log(R)                    + c   (R = loop resolvent)
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from generalize import admm_float, admm_fixed, snap_lat, A_op, KAPPA, BOXHI, GAMMA
from loop_gain import system_cond, resolvent, N, F, q2_12

FIT_TRIALS, FIT_SEED = 20, 7000          # identical to the published fit
HELD_TRIALS, HELD_SEED = 25, 20000       # disjoint seeds
CONDS = list(np.geomspace(1.0, 300.0, 16))
QS = (0.50, 0.90, 0.95, 0.99)


def one(c, seed, mode):
    M, q, a = system_cond(c, seed)
    kap, hi, gam = snap_lat(KAPPA * a, F), snap_lat(BOXHI * a, F), snap_lat(GAMMA, F)
    zr, vs = admm_float(M, q, mode, N, kap, hi, gam)
    zf = admm_fixed(M, q, mode, N, F, kap, hi, gam)
    d = (np.mean(np.abs(vs) <= kap) if mode == 0 else
         np.mean(np.abs(vs) >= hi) if mode == 1 else 0.0)
    return dict(mse=float(np.mean((zf - zr) ** 2)), A=float(A_op(mode, d, np.mean(vs ** 2))),
                d=float(d), nm=float(np.linalg.norm(M, 2)),
                R=float(resolvent(M, GAMMA if mode == 2 else 1.0)))


def features(mode, r):
    base = np.log(1.0 / (1.0 - r["nm"] + 1e-6))
    if mode == 0: return [base, r["d"], 1.0]
    if mode == 1: return [base, r["d"] ** 2, 1.0]
    return [np.log(r["R"]), 1.0]


def collect(seed, T, mode):
    """Per-condition cells: arithmetic- and geometric-mean log G plus per-instance rows."""
    cells = []
    for c in CONDS:
        rs = [one(c, seed + t, mode) for t in range(T)]
        good = [r for r in rs if r["mse"] > 0 and r["A"] > 0]
        lg = [np.log(r["mse"] / q2_12 / r["A"]) for r in good]
        mse = np.array([r["mse"] for r in rs])
        m = dict(nm=np.mean([r["nm"] for r in rs]), d=np.mean([r["d"] for r in rs]),
                 R=np.mean([r["R"] for r in rs]))
        cells.append(dict(feat=features(mode, m),
                          arith=np.log(mse.mean() / q2_12 / np.mean([r["A"] for r in rs])),
                          geo=float(np.mean(lg)),
                          top=float(mse.max() / mse.sum()) if mse.sum() > 0 else 0.0,
                          per=[(l, features(mode, r)) for l, r in zip(lg, good)],
                          zero=len(rs) - len(good)))
    return cells


def main():
    b = lambda v: v / (2 * np.log(2))              # natural-log G -> bits of width
    out = {}
    for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
        fit = collect(FIT_SEED, FIT_TRIALS, mode)
        held = collect(HELD_SEED, HELD_TRIALS, mode)
        extra = [collect(s, FIT_TRIALS, mode) for s in (30000, 40000, 50000)]
        X = np.array([c["feat"] for c in fit])
        res = {"top_instance_share_median": float(np.median([c["top"] for c in fit]))}
        for stat in ("arith", "geo"):
            y = np.array([c[stat] for c in fit])
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            fe = b(np.mean(np.abs(y - X @ coef)))
            he = b(np.mean([abs(c[stat] - np.dot(c["feat"], coef)) for c in held]))
            sets = np.array([[c[stat] for c in cs] for cs in [fit, held] + extra])
            sd = b(float(np.std(sets, axis=0, ddof=1).mean()))
            per = np.array([b(l - np.dot(f, coef)) for c in held for l, f in c["per"]])
            qv = np.quantile(per, QS)
            res[stat] = dict(coef=[float(v) for v in coef], fit_err=float(fe),
                             heldout_err=float(he), seed_sd=sd,
                             quantiles={f"p{int(q*100)}": float(v) for q, v in zip(QS, qv)},
                             max=float(per.max()), frac_over_half=float(np.mean(per > 0.5)),
                             n=int(len(per)))
            print(f"{nm:4s} {stat:5s} fit {fe:.3f} | HELD-OUT {he:.3f} | seed sd {sd:.3f} bits"
                  f" | per-inst " + " ".join(f"p{int(q*100)} {v:+.2f}" for q, v in zip(QS, qv))
                  + f"  max {per.max():+.2f}", flush=True)
        print(f"{nm:4s}       largest single instance = {res['top_instance_share_median']:.0%}"
              " of ensemble MSE (median cell)")
        out[nm] = res
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "results",
                                     "margin.json"), "w"), indent=1)
    print("\n  saved -> results/margin.json")


if __name__ == "__main__":
    main()
