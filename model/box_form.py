"""
box_form.py -- P0.2a falsifier: is the L1/Box sign flip a MECHANISM or a fit?

THE PROBLEM. loop_gain_l1.py closed both operators using d as a second
regressor, but with opposite coefficients: +20.6 for L1, -20.4 for Box. A
single statistic pushing two operators in opposite directions is a curve fit
unless there is a reason. Box also prefers d^2 (LOO 0.178) over d (0.234), so
its functional form is unsettled too.

THE HYPOTHESIS (H). d counts different things in the two operators:

  L1  : d = fraction with |v| <= kappa, i.e. entries the soft threshold sends
        to zero. These sit ON the threshold boundary and can flip in and out
        of the zero set from iteration to iteration -> CHURN -> destabilising.
  Box : d = fraction with |v| >= hi, i.e. entries pinned to the clip bound.
        A pinned entry stays pinned -> FROZEN -> stabilising, which is what
        Sprint 1 already found ("clipping is stabilising", exponent 0.5).

If H holds, the thing that actually drives the error is not d but CHURN --
how often membership of the degenerate set CHANGES:

    c = mean_t [ fraction of coordinates whose membership differs
                 between iteration t and t+1 ]

PREDICTIONS, each of which can fail:

  P1. c is substantial for L1 and near zero for Box.
      FAILS H if Box churns as much as L1.
  P2. c enters with the SAME sign for both operators.
      FAILS H if the sign flip survives when d is replaced by c.
  P3. c is at least as good a regressor as d (LOO <= 0.5 bits for both).
      FAILS H if the mechanism-motivated quantity fits worse than the
      shape-free one -- that would mean d works for reasons unrelated to
      churn, and neither functional form should be claimed.

If P1-P3 all hold, the theorem set can state ONE mechanism with one sign and
Box's form follows. If any fails, the honest outcome is to report d
empirically per operator and claim no mechanism.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from generalize import (admm_fixed, snap_lat, A_op, RHO, MAX_IT,
                        KAPPA, BOXHI, GAMMA)
from loop_gain import system_cond, resolvent, N, F, q2_12

TRIALS = 20
CONDS = list(np.geomspace(1.0, 300.0, 16))
CRIT = 0.5


def admm_float_masks(M, q, mode, n, kap, hi, gam, iters=MAX_IT):
    """admm_float, additionally returning the per-iteration degenerate mask.

    Mirrors generalize.admm_float exactly; only the mask bookkeeping is new.
    """
    z, u = np.zeros(n), np.zeros(n)
    vs, masks = [], []
    for _ in range(iters):
        x = M @ (q + RHO * (z - u))
        v = x + u
        vs.append(v.copy())
        if mode == 0:
            mask = np.abs(v) <= kap
            zn = np.sign(v) * np.maximum(np.abs(v) - kap, 0.0)
        elif mode == 1:
            mask = np.abs(v) >= hi
            zn = np.clip(v, -hi, hi)
        else:
            mask = np.zeros(n, dtype=bool)
            zn = gam * v
        masks.append(mask)
        u, z = u + x - zn, zn
    return z, np.concatenate(vs), np.array(masks)


def churn(masks, tail=True):
    """Fraction of coordinates changing degenerate-set membership per step."""
    m = masks[len(masks) // 2:] if tail else masks
    if len(m) < 2:
        return 0.0
    return float(np.mean([np.mean(m[t] != m[t + 1]) for t in range(len(m) - 1)]))


def collect():
    rows = []
    print(f"{'cond':>7s} {'op':4s} {'G':>11s} {'d':>7s} {'churn':>7s} "
          f"{'churn_all':>10s}")
    for c in CONDS:
        for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
            mses, As, nms, res, ds, cs, cs_all = [], [], [], [], [], [], []
            for t in range(TRIALS):
                M, q, a = system_cond(c, 7000 + t)
                kap = snap_lat(KAPPA * a, F)
                hi = snap_lat(BOXHI * a, F)
                gam = snap_lat(GAMMA, F)
                zr, vs, masks = admm_float_masks(M, q, mode, N, kap, hi, gam)
                zf = admm_fixed(M, q, mode, N, F, kap, hi, gam)
                d = float(np.mean(masks))
                mses.append(np.mean((zf - zr) ** 2))
                As.append(A_op(mode, d, np.mean(vs ** 2)))
                nms.append(np.linalg.norm(M, 2))
                res.append(resolvent(M, GAMMA if mode == 2 else 1.0))
                ds.append(d)
                cs.append(churn(masks, tail=True))
                cs_all.append(churn(masks, tail=False))
            r = dict(cond=float(c), op=nm, mode=mode,
                     G=float(np.mean(mses) / q2_12 / np.mean(As)),
                     nm=float(np.mean(nms)), res=float(np.mean(res)),
                     d=float(np.mean(ds)), churn=float(np.mean(cs)),
                     churn_all=float(np.mean(cs_all)))
            rows.append(r)
            print(f"{c:7.1f} {nm:4s} {r['G']:11.1f} {r['d']:7.4f} "
                  f"{r['churn']:7.4f} {r['churn_all']:10.4f}")
    return rows


def bits(resid):
    return float(np.mean(np.abs(resid)) / (2 * np.log(2)))


def fit_eval(X, y):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    ins = bits(y - X @ coef)
    loo = []
    for i in range(len(y)):
        k = np.arange(len(y)) != i
        c2, *_ = np.linalg.lstsq(X[k], y[k], rcond=None)
        loo.append(y[i] - X[i] @ c2)
    return ins, bits(np.array(loo)), coef


def main():
    rows = collect()
    out = {"trials": TRIALS, "conds": CONDS, "rows": rows, "fits": {}}

    print(f"\n{'='*70}")
    print("P1: is Box frozen and L1 churning?")
    print(f"{'='*70}")
    for nm in ("L1", "Box"):
        rr = [r for r in rows if r["op"] == nm]
        ch = np.array([r["churn"] for r in rr])
        dd = np.array([r["d"] for r in rr])
        print(f"  {nm:4s} churn: min {ch.min():.4f}  max {ch.max():.4f}  "
              f"mean {ch.mean():.4f}   (d ranges {dd.min():.3f}-{dd.max():.3f})")
        out["fits"].setdefault(nm, {})["churn_range"] = [float(ch.min()),
                                                         float(ch.max())]

    print(f"\n{'='*70}")
    print("P2/P3: does churn unify the sign, and does it fit?")
    print(f"{'='*70}")
    print(f"{'op':4s} {'regressor':>12s} {'coef':>10s} {'in-samp':>9s} "
          f"{'LOO':>8s} {'verdict':>8s}")
    for nm in ("L1", "Box"):
        rr = [r for r in rows if r["op"] == nm]
        y = np.log(np.array([r["G"] for r in rr]))
        base = np.log(1.0 / (1.0 - np.array([r["nm"] for r in rr]) + 1e-6))
        ones = np.ones_like(base)
        cands = {
            "none": None,
            "d": np.array([r["d"] for r in rr]),
            "d^2": np.array([r["d"] for r in rr]) ** 2,
            "churn": np.array([r["churn"] for r in rr]),
            "churn_all": np.array([r["churn_all"] for r in rr]),
        }
        for label, R in cands.items():
            if R is None:
                X = np.vstack([base, ones]).T
            elif np.ptp(R) < 1e-12:
                continue
            else:
                X = np.vstack([base, R, ones]).T
            ins, loo, coef = fit_eval(X, y)
            cf = "--" if R is None else f"{coef[1]:10.3f}"
            print(f"{nm:4s} {label:>12s} {cf:>10s} {ins:9.3f} {loo:8.3f} "
                  f"{'PASS' if loo <= CRIT else 'fail':>8s}")
            out["fits"].setdefault(nm, {}).setdefault("cands", []).append(
                dict(R=label, in_sample=ins, loo=loo,
                     coef=[float(v) for v in coef]))

    os.makedirs("results", exist_ok=True)
    json.dump(out, open("results/box_form.json", "w"), indent=1)
    print("\n  saved -> results/box_form.json")


if __name__ == "__main__":
    main()
