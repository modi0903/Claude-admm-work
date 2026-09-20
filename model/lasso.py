"""
lasso.py -- second demonstration problem: sparse regression (LASSO).

    minimise  0.5*||A x - b||^2 + lam*||x||_1

WHY. Every result so far comes from one problem family (MIMO-style detection).
A reviewer's first question is whether any of it transfers. LASSO is the
canonical proximal problem, and it maps onto the EXISTING hardware unchanged:
ADMM's x-update is x = M(q + rho(z - u)) with M = (A'A + rho I)^-1, q = A'b,
and the z-update is the L1 lane with kappa = lam/rho. Same datapath, same RTL.

It is also a HARDER test than it looks. On the MIMO workload the L1 lane's
degenerate fraction d sits near 0 (error_decomp.py: d = 0.000), so Theorem 1's
(1-d) term was only ever exercised for L1 by annihilation.py, which sweeps
kappa against a MIMO-derived input distribution with kappa placed exactly on
the lattice. LASSO produces SPARSE solutions, so d is naturally high, and
kappa lands wherever lam puts it -- off the lattice.

PREDICTIONS, registered before running:
  P-L1  On LASSO's native v-distribution, Theorem 1 predicts L1 lane error to
        within 10% (T1/meas in [0.9, 1.1]) across the lam range, while the
        classical q^2/12 model is off by ~1/(1-d).
  P-L2  Width need tracks how well-determined the problem is. m=32 rows for
        N=8 unknowns: F* <= 9 (the MIMO design point suffices). m=6
        (underdetermined, ||M||2 -> 1/rho, loop gain grows): F* > 9.
  P-L3  At F*, the recovered SUPPORT matches double precision on >= 99% of
        instances.
  (P-L4, RTL bit-exact on LASSO vectors, is in gen_vectors_lasso.py.)
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import fxp_admm as FX
from fxp_admm import ProxConfig, prox_l1, to_fx, to_fl, admm_float
from main_sweep import run_fixed, snap

N, RHO, MAX_IT = 8, 1.0, 64
ALPHA_TARGET = 0.95
HERE = os.path.dirname(__file__)


def lasso_system(seed, m=16, k=2, snr_db=20.0, lam_frac=0.2):
    """k-sparse ground truth, Gaussian design. Returns scaled M, q, kappa.

    lam is set relative to lam_max = ||A'b||_inf (lam >= lam_max gives the
    all-zero solution). Scaling q by alpha scales the solution by alpha and the
    threshold with it (Lemma 1, homogeneity), so kappa = alpha*lam/rho.
    """
    rng = np.random.default_rng(seed)
    A = rng.standard_normal((m, N)) / np.sqrt(m)
    x0 = np.zeros(N)
    sup = rng.choice(N, k, replace=False)
    x0[sup] = rng.choice([-1.0, 1.0], k) * rng.uniform(0.5, 1.5, k)
    y = A @ x0
    b = y + rng.standard_normal(m) * np.sqrt(np.mean(y ** 2) / 10 ** (snr_db / 10))
    M = np.linalg.inv(A.T @ A + RHO * np.eye(N))
    q = A.T @ b
    lam = lam_frac * np.max(np.abs(q))
    # rho-aware range scaling, as in sweep_ordering.system
    al = min(1.0, ALPHA_TARGET / ((1.0 + RHO) * max(np.abs(q).max(), 1e-9)))
    return M, q * al, lam * al / RHO, x0, al


# ---------------------------------------------------------------- P-L1
def e1_operator(lam_fracs=(0.05, 0.1, 0.2, 0.3, 0.5), trials=60, m=16,
                fs=range(6, 13)):
    """Theorem 1 on LASSO's native distribution, kappa wherever lam puts it."""
    print("P-L1  Theorem 1 on the native LASSO distribution (L1 lane, m=16)")
    print(f"  {'lam/lam_max':>11s} {'d':>6s} {'T1/meas':>8s} {'classical/meas':>15s} "
          f"{'1/(1-d)':>8s}")
    rows = []
    for lf in lam_fracs:
        meas = {f: 0.0 for f in fs}; t1 = {f: 0.0 for f in fs}
        cls = {f: 0.0 for f in fs}; nD, nT = 0, 0
        for t in range(trials):
            M, q, kap, _, _ = lasso_system(31000 + t, m=m, lam_frac=lf)
            z = np.zeros(N); u = np.zeros(N); vs = []
            for _ in range(MAX_IT):
                x = M @ (q + RHO * (z - u)); v = x + u; vs.append(v.copy())
                zn = np.sign(v) * np.maximum(np.abs(v) - kap, 0.0)
                u = u + x - zn; z = zn
            v_fx = [to_fx(x) for x in np.concatenate(vs)]      # lane input at Q2.16
            v_ref = np.array([to_fl(x) for x in v_fx])
            kq = to_fx(kap); k_ex = to_fl(kq)                   # kappa as specified
            D = np.abs(v_ref) <= k_ex
            nD += int(D.sum()); nT += len(v_ref)
            z_ex = np.sign(v_ref) * np.maximum(np.abs(v_ref) - k_ex, 0.0)
            for f in fs:
                cfg = ProxConfig(f_l1=f, kappa_q16=kq)
                zf = np.array([to_fl(prox_l1(x, cfg)) for x in v_fx])
                qq = 2.0 ** -f
                dk = to_fl(cfg.kappa, f) - k_ex                 # kappa lattice error
                meas[f] += float(np.sum((zf - z_ex) ** 2))
                t1[f] += float((~D).sum()) * (qq * qq / 12 + dk * dk)
                cls[f] += len(v_ref) * qq * qq / 12
        d = nD / nT
        r1 = np.mean([t1[f] / meas[f] for f in fs if meas[f] > 0])
        rc = np.mean([cls[f] / meas[f] for f in fs if meas[f] > 0])
        print(f"  {lf:11.2f} {d:6.3f} {r1:8.3f} {rc:15.2f} {1/(1-d):8.2f}", flush=True)
        rows.append(dict(lam_frac=lf, d=d, t1_ratio=float(r1), classical_ratio=float(rc)))
    return rows


# ---------------------------------------------------------------- P-L2/3
def e2_width(ms=(6, 8, 16, 32), lam_fracs=(0.1, 0.2, 0.3), trials=40,
             fms=range(6, 15), target=1e-4):
    """Main-datapath width F* (lanes tied to F, as in main_sweep 'uniform')
    and support agreement with double precision."""
    print("\nP-L2/P-L3  design width and support recovery (lanes = F_MAIN)")
    print(f"  {'m':>3s} {'lam':>5s} {'||M||2':>7s} | {'F*':>3s} | support match "
          f"at F*  /  at F=9  | recovers x0 (float) | sat")
    rows = []
    for m in ms:
        for lf in lam_fracs:
            FX.sat_reset()
            per_f = {f: dict(nmse=[], sup=[]) for f in fms}
            nms, rec = [], []
            for t in range(trials):
                M, q, kap, x0, _ = lasso_system(7000 + t, m=m, lam_frac=lf)
                nms.append(np.linalg.norm(M, 2))
                zr, _, _ = admm_float(M, q, 0, N, kappa=kap, rho=RHO,
                                      max_iter=MAX_IT, eps=0.0)
                sr = np.abs(zr) > 1e-9
                rec.append(bool(np.array_equal(sr, x0 != 0)))
                for f in fms:
                    k = snap(kap, f)
                    zr2, _, _ = admm_float(M, q, 0, N, kappa=k, rho=RHO,
                                           max_iter=MAX_IT, eps=0.0)
                    zf = run_fixed(M, q, 0, f, f, f, f, k, 1.0, 0.667, iters=MAX_IT)
                    d2 = np.linalg.norm(zr2) ** 2
                    per_f[f]["nmse"].append(np.linalg.norm(zf - zr2) ** 2 /
                                            (d2 if d2 > 1e-12 else 1.0))
                    per_f[f]["sup"].append(bool(np.array_equal(
                        np.abs(zf) > 0, np.abs(zr2) > 1e-9)))
            fstar = next((f for f in fms if np.mean(per_f[f]["nmse"]) <= target), None)
            s_star = np.mean(per_f[fstar]["sup"]) if fstar else float("nan")
            s9 = np.mean(per_f[9]["sup"])
            sat = int(FX.SAT_COUNT[0])
            print(f"  {m:3d} {lf:5.2f} {np.mean(nms):7.3f} | {str(fstar):>3s} | "
                  f"{s_star:13.1%}  /  {s9:6.1%} | {np.mean(rec):19.1%} | {sat}"
                  + ("  !! SAT" if sat else ""), flush=True)
            rows.append(dict(m=m, lam_frac=lf, norm_M=float(np.mean(nms)), fstar=fstar,
                             support_at_fstar=float(s_star), support_at_9=float(s9),
                             float_recovers_x0=float(np.mean(rec)), sat=sat,
                             nmse={f: float(np.mean(per_f[f]["nmse"])) for f in fms}))
    return rows


# ---------------------------------------------------------------- P-L3 post-hoc
def e3_mismatch(ms=(6, 8, 16, 32), lam_fracs=(0.1, 0.2, 0.3), trials=40):
    """POST-HOC (written after P-L3 failed as registered). For every support
    disagreement at F*, how large is the disagreeing coefficient, in LSBs of F*?
    A coefficient within ~1 LSB of zero sits at the threshold boundary: the
    fixed-point and double-precision solvers disagree about a value that is
    below the resolution of the format. This characterises the failure; it
    does not rescue the registered prediction."""
    fst = {(r["m"], r["lam_frac"]): r["fstar"]
           for r in json.load(open(os.path.join(HERE, "..", "results", "lasso.json")))["e2"]}
    print("\nP-L3 post-hoc  size of support-disagreeing coefficients, in LSB of F*")
    lsbs = []
    for m in ms:
        for lf in lam_fracs:
            f = fst[(m, lf)]
            for t in range(trials):
                M, q, kap, _, _ = lasso_system(7000 + t, m=m, lam_frac=lf)
                k = snap(kap, f)
                zr2, _, _ = admm_float(M, q, 0, N, kappa=k, rho=RHO,
                                       max_iter=MAX_IT, eps=0.0)
                zf = run_fixed(M, q, 0, f, f, f, f, k, 1.0, 0.667, iters=MAX_IT)
                bad = (np.abs(zf) > 0) != (np.abs(zr2) > 1e-9)
                for i in np.flatnonzero(bad):
                    lsbs.append(max(abs(zf[i]), abs(zr2[i])) / 2.0 ** -f)
    lsbs = np.array(lsbs)
    n = len(lsbs)
    print(f"  mismatched coefficients: {n}   max {lsbs.max():.2f} LSB   "
          f"<=1 LSB {np.mean(lsbs <= 1):.0%}   <=2 LSB {np.mean(lsbs <= 2):.0%}")
    return dict(n=n, max_lsb=float(lsbs.max()), frac_le1=float(np.mean(lsbs <= 1)),
                frac_le2=float(np.mean(lsbs <= 2)), lsb=[float(x) for x in lsbs])


def main():
    if "--e3" in sys.argv:          # post-hoc only; needs e2 results on disk
        path = os.path.join(HERE, "..", "results", "lasso.json")
        out = json.load(open(path)); out["e3"] = e3_mismatch()
        json.dump(out, open(path, "w"), indent=1, default=float)
        return
    out = {"e1": e1_operator(), "e2": e2_width()}
    out["e3"] = None
    json.dump(out, open(os.path.join(HERE, "..", "results", "lasso.json"), "w"),
              indent=1, default=float)
    print("\n  saved -> results/lasso.json   (run again with --e3 for the post-hoc)")


if __name__ == "__main__":
    main()
