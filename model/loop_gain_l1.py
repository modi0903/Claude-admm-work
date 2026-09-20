"""
loop_gain_l1.py -- falsifier for the L1 active-set term (TODO P0.1).

Sprint 1b left L1 at 0.834 bits against a 0.5-bit criterion, with the
hypothesis that the residual is active-set churn and that d is the missing
regressor.

This script tests that hypothesis and is written to be able to REJECT it:

  1. d is averaged over trials. loop_gain.py records d from the last trial
     only while averaging every other quantity over 20; as a regressor that
     noise is not acceptable.
  2. The conditioning grid is denser (16 points, not 8). Adding a second
     regressor to 8 points improves in-sample error almost automatically.
  3. Every fit is scored by LEAVE-ONE-OUT cross-validation as well as
     in-sample. The 0.5-bit criterion is applied to the LOO number. An
     in-sample pass with a LOO fail is overfitting and is reported as a
     failure.

Baseline (one regressor):  log G = a*log(1/(1-||M||2)) + b
Candidate (two):           log G = a*log(1/(1-||M||2)) + c*R(d) + b

R(d) candidates are churn proxies. d -> 1 means the active set is frozen
(fully degenerate, no churn); d -> 0 means fully inactive. Churn should peak
in between, so d(1-d) is the shape-motivated candidate; the others are
included so the motivated one is not the only thing tried.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from generalize import (admm_float, admm_fixed, snap_lat, A_op,
                        RHO, KAPPA, BOXHI, GAMMA, ALPHA_TARGET)
from loop_gain import system_cond, resolvent, N, F, q2_12

TRIALS = 20
CONDS = list(np.geomspace(1.0, 300.0, 16))
CRIT = 0.5


def collect():
    rows = []
    print(f"{'cond':>7s} {'op':4s} {'G_meas':>12s} {'||M||2':>8s} "
          f"{'resolv':>10s} {'d_mean':>8s} {'d_sd':>7s}")
    for c in CONDS:
        for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
            mses, As, nms, res, ds = [], [], [], [], []
            for t in range(TRIALS):
                M, q, a = system_cond(c, 7000 + t)
                kap = snap_lat(KAPPA * a, F)
                hi = snap_lat(BOXHI * a, F)
                gam = snap_lat(GAMMA, F)
                zr, vs = admm_float(M, q, mode, N, kap, hi, gam)
                zf = admm_fixed(M, q, mode, N, F, kap, hi, gam)
                d = (np.mean(np.abs(vs) <= kap) if mode == 0 else
                     np.mean(np.abs(vs) >= hi) if mode == 1 else 0.0)
                mses.append(np.mean((zf - zr) ** 2))
                As.append(A_op(mode, d, np.mean(vs ** 2)))
                nms.append(np.linalg.norm(M, 2))
                res.append(resolvent(M, GAMMA if mode == 2 else 1.0))
                ds.append(d)                       # averaged, unlike loop_gain.py
            r = dict(cond=float(c), op=nm, mode=mode,
                     G=float(np.mean(mses) / q2_12 / np.mean(As)),
                     nm=float(np.mean(nms)), res=float(np.mean(res)),
                     d=float(np.mean(ds)), d_sd=float(np.std(ds)),
                     A=float(np.mean(As)))
            rows.append(r)
            print(f"{c:7.1f} {nm:4s} {r['G']:12.1f} {r['nm']:8.4f} "
                  f"{r['res']:10.2f} {r['d']:8.4f} {r['d_sd']:7.4f}")
    return rows


def bits(resid):
    return float(np.mean(np.abs(resid)) / (2 * np.log(2)))


def fit_eval(X, y):
    """In-sample and leave-one-out mean |error| in bits for design matrix X."""
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

    print(f"\n{'='*74}")
    print("log G = a*log(1/(1-||M||2)) + c*R(d) + b     "
          f"criterion: LOO <= {CRIT} bits")
    print(f"{'='*74}")
    print(f"{'op':4s} {'R(d)':>14s} {'c':>9s} {'in-samp':>9s} "
          f"{'LOO':>8s} {'verdict':>9s}")

    for nm in ("L1", "Box", "L2"):
        rr = [r for r in rows if r["op"] == nm]
        y = np.log(np.array([r["G"] for r in rr]))
        d = np.array([r["d"] for r in rr])
        base = np.log(1.0 / (1.0 - np.array([r["nm"] for r in rr]) + 1e-6))
        ones = np.ones_like(base)

        cands = {"none (baseline)": None,
                 "d": d,
                 "d(1-d)": d * (1 - d),
                 "-log(1-d)": -np.log(np.clip(1 - d, 1e-6, None)),
                 "d^2": d ** 2}

        for label, R in cands.items():
            if R is None:
                X = np.vstack([base, ones]).T
            elif np.ptp(R) < 1e-12:
                print(f"{nm:4s} {label:>14s} {'--':>9s} {'--':>9s} "
                      f"{'--':>8s} {'no var':>9s}")
                continue
            else:
                X = np.vstack([base, R, ones]).T
            ins, loo, coef = fit_eval(X, y)
            c = "--" if R is None else f"{coef[1]:9.3f}"
            verdict = "PASS" if loo <= CRIT else "fail"
            print(f"{nm:4s} {label:>14s} {c:>9s} {ins:9.3f} "
                  f"{loo:8.3f} {verdict:>9s}")
            out["fits"].setdefault(nm, []).append(
                dict(R=label, in_sample=ins, loo=loo,
                     coef=[float(v) for v in coef]))

    os.makedirs("results", exist_ok=True)
    json.dump(out, open("results/loop_gain_l1.json", "w"), indent=1)
    print("\n  saved -> results/loop_gain_l1.json")


if __name__ == "__main__":
    main()
