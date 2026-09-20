"""
loop_gain.py -- model the loop amplification G exposed by Sprint 1.

Sprint 1 showed MSE = G * A_op * q^2/12 with G spanning 4 orders of magnitude.
G(L2) was nearly invariant (7-23); G(L1), G(Box) ran 46 -> 196,457.

For a LINEAR fixed-point iteration s <- T s + e with injected noise e, the
steady-state error variance is set by the resolvent: ||(I-T)^-1||^2. ADMM with
a linear prox (L2) IS such an iteration, and T can be written exactly:

    s = (z, u)
    T = [[ g*rho*M      ,  g*(I - rho*M)     ],
         [ (1-g)*rho*M  ,  (1-g)*(I - rho*M) ]]        g = gamma

For Box and L1 the map is piecewise linear: on the inactive set the operator is
the identity (g = 1); on the degenerate set the output is frozen. So the
effective g is not a constant but depends on d. We test whether the resolvent
of T(g_eff) predicts G, with g_eff = gamma for L2 and g_eff = 1 for L1/Box.

Condition number is swept CONTINUOUSLY rather than as two discrete ensembles,
so the trend is visible rather than two points.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from generalize import (admm_float, admm_fixed, snap_lat, A_op,
                        RHO, MAX_IT, KAPPA, BOXHI, GAMMA, ALPHA_TARGET)

N, F, TRIALS = 8, 10, 20
CONDS = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 300.0]
q2_12 = (2.0 ** -F) ** 2 / 12.0


def system_cond(c, seed):
    rng = np.random.default_rng(seed)
    nr = 4 * N
    H = rng.standard_normal((nr, N)) / np.sqrt(nr)
    if c > 1.0:
        U, s, Vt = np.linalg.svd(H, full_matrices=False)
        s = np.geomspace(s[0], s[0] / c, len(s))
        H = U @ np.diag(s) @ Vt
    x = rng.choice([-1.0, 1.0], N)
    p = np.linalg.norm(H @ x) ** 2 / nr
    y = H @ x + rng.standard_normal(nr) * np.sqrt(p / 10 ** 1.2)
    M = np.linalg.inv(H.T @ H + RHO * np.eye(N))
    q = H.T @ y
    a = min(1.0, ALPHA_TARGET / max(np.abs(q).max(), 1e-9))
    return M, q * a, a


def resolvent(M, g):
    """||(I - T)^-1||_2 for the linearised ADMM map with prox gain g."""
    I = np.eye(N)
    A, B = RHO * M, I - RHO * M
    T = np.block([[g * A, g * B], [(1 - g) * A, (1 - g) * B]])
    try:
        return np.linalg.norm(np.linalg.inv(np.eye(2 * N) - T), 2)
    except np.linalg.LinAlgError:
        return np.inf


def main():
    # Guarded: this module is imported by loop_gain_l1, box_form, adversarial
    # and t2_crossover for system_cond/resolvent. Without the guard every
    # import silently re-ran this whole sweep and overwrote
    # results/loop_gain.json.
    rows = []
    print(f"{'cond':>6s} {'op':4s} {'G_meas':>12s} {'||M||2':>8s} "
          f"{'rho(I-rM)':>10s} {'resolv':>10s} {'d':>7s}")
    for c in CONDS:
        for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
            mses, As, nms, sps, res, ds = [], [], [], [], [], []
            for t in range(TRIALS):
                M, q, a = system_cond(c, 7000 + t)
                kap, hi, gam = (snap_lat(KAPPA*a, F), snap_lat(BOXHI*a, F), snap_lat(GAMMA, F))
                zr, vs = admm_float(M, q, mode, N, kap, hi, gam)
                zf = admm_fixed(M, q, mode, N, F, kap, hi, gam)
                d = (np.mean(np.abs(vs) <= kap) if mode == 0 else
                     np.mean(np.abs(vs) >= hi) if mode == 1 else 0.0)
                mses.append(np.mean((zf - zr) ** 2))
                As.append(A_op(mode, d, np.mean(vs ** 2)))
                nms.append(np.linalg.norm(M, 2))
                sps.append(max(abs(np.linalg.eigvals(np.eye(N) - RHO * M))))
                res.append(resolvent(M, GAMMA if mode == 2 else 1.0))
                ds.append(d)          # averaged like every other quantity
            G = float(np.mean(mses) / q2_12 / np.mean(As))
            r = dict(cond=c, op=nm, mode=mode, G=G, nm=float(np.mean(nms)),
                     sp=float(np.mean(sps)), res=float(np.mean(res)),
                     d=float(np.mean(ds)), A=float(np.mean(As)))
            rows.append(r)
            print(f"{c:6.0f} {nm:4s} {G:12.1f} {r['nm']:8.4f} {r['sp']:10.4f} "
                  f"{r['res']:10.2f} {r['d']:7.4f}")

    print("\nlog-log fit  log G = a*log(pred) + b,  per operator")
    print(f"{'op':4s} {'predictor':>12s} {'slope':>8s} {'R^2':>7s} {'mean|err| bits':>15s}")
    best = {}
    for nm in ("L1", "Box", "L2"):
        rr = [r for r in rows if r["op"] == nm]
        g = np.log(np.array([r["G"] for r in rr]))
        for pname in ("res", "nm_inv", "sp_inv"):
            if pname == "res":      p = np.array([r["res"] for r in rr])
            elif pname == "nm_inv": p = 1.0 / (1.0 - np.array([r["nm"] for r in rr]) + 1e-6)
            else:                   p = 1.0 / (1.0 - np.array([r["sp"] for r in rr]) + 1e-6)
            lp = np.log(p)
            A_ = np.vstack([lp, np.ones_like(lp)]).T
            coef, *_ = np.linalg.lstsq(A_, g, rcond=None)
            pred = A_ @ coef
            ss = 1 - np.sum((g - pred) ** 2) / np.sum((g - g.mean()) ** 2)
            eb = float(np.mean(np.abs(g - pred)) / (2 * np.log(2)))
            print(f"{nm:4s} {pname:>12s} {coef[0]:8.3f} {ss:7.3f} {eb:15.3f}")
            if nm not in best or eb < best[nm][1]:
                best[nm] = (pname, eb, float(coef[0]), float(ss))

    print("\nbest predictor per operator:")
    for nm, (pn, eb, sl, ss) in best.items():
        print(f"  {nm:4s}  {pn:8s}  slope {sl:6.2f}  R^2 {ss:5.3f}  "
              f"mean err {eb:.3f} bits")
    json.dump({"rows": rows, "best": {k: list(v) for k, v in best.items()}},
              open("results/loop_gain.json", "w"), indent=1)


if __name__ == "__main__":
    main()
