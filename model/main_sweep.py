"""
main_sweep.py -- closes caveat C.4.

Every F* so far was measured with the main datapath pinned at Q2.16 while one
lane varied. That isolates the lane correctly but says nothing about how narrow
the MAIN path can be. Narrowing the main path and the lanes together compounds
their errors, so the array width cannot be set from the lane results.

Here the full datapath is parameterised: weights M, vector q, the systolic
accumulator, x, v, z, u and the residuals all scale with F_M. Lanes are then
either pinned at the derived triple (8/7/8) or tied to F_M.

This matters because the array is 472 LUTs + 64 DSPs and the pre-combine /
dual-update / residual logic is ~2735 LUTs -- far more than the 1232 in the
proximal lanes. If F_M can drop, that is the largest remaining saving.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import _sat, q_narrow, q_widen, admm_float
from experiments import system, N, RHO

INT_BITS, ACC_INT, MAX_IT = 2, 8, 64
KAPPA, BOXHI, GAMMA = 0.10, 1.00, 0.667


def fx(x, f, w):
    return _sat(int(np.floor(x * (1 << f) + 0.5)), w)


def fl(x, f):
    return x / float(1 << f)


def snap(val, f_lane):
    """Put a constant on the lane lattice (Appendix B.3)."""
    return round(val * (1 << f_lane)) / float(1 << f_lane)


def sadd(a, b, w, sub=False):
    return _sat(a - b if sub else a + b, w)


def run_fixed(M, q, mode, f_m, f_l1, f_box, f_l2, kap, hi, gam, iters=MAX_IT):
    w_m = INT_BITS + f_m
    f_acc, w_acc = 2 * f_m, ACC_INT + 2 * f_m
    # lanes can never be wider than the path feeding them
    f_l1, f_box, f_l2 = min(f_l1, f_m), min(f_box, f_m), min(f_l2, f_m)
    w_l1, w_box, w_l2 = (INT_BITS + f_l1, INT_BITS + f_box, INT_BITS + f_l2)

    M_fx = [fx(v, f_m, w_m) for v in np.asarray(M).ravel()]
    q_fx = [fx(v, f_m, w_m) for v in np.asarray(q).ravel()]
    kap_fx = fx(kap, f_l1, w_l1)
    hi_fx = fx(hi, f_box, w_box)
    gam_fx = fx(gam, f_l2, w_l2)

    z = [0] * N
    u = [0] * N
    for _ in range(iters):
        w = [sadd(q_fx[i], sadd(z[i], u[i], w_m, sub=True), w_m) for i in range(N)]
        x = []
        for i in range(N):
            acc = sum(M_fx[i * N + j] * w[j] for j in range(N))
            assert abs(acc) < (1 << (w_acc - 1)), "accumulator overflow"
            x.append(q_narrow(acc, f_acc, w_m, f_m))
        v = [sadd(x[i], u[i], w_m) for i in range(N)]

        zn = []
        for i in range(N):
            if mode == 0:
                a = q_narrow(v[i], f_m, w_l1, f_l1)
                m = max(abs(a) - kap_fx, 0)
                r = _sat(-m if a < 0 else m, w_l1)
                zn.append(q_widen(r, f_l1, f_m))
            elif mode == 1:
                a = q_narrow(v[i], f_m, w_box, f_box)
                zn.append(q_widen(min(max(a, -hi_fx), hi_fx), f_box, f_m))
            else:
                a = q_narrow(v[i], f_m, w_l2, f_l2)
                r = q_narrow(a * gam_fx, 2 * f_l2, w_l2, f_l2)
                zn.append(q_widen(r, f_l2, f_m))

        u = [sadd(u[i], sadd(x[i], zn[i], w_m, sub=True), w_m) for i in range(N)]
        z = zn
    return np.array([fl(e, f_m) for e in z])


def sweep(mode, lanes, label, trials=40):
    print(f"\n--- {label} ---")
    print("   F_M    NMSE        abs MSE")
    out = {}
    for f_m in range(6, 17):
        ne, ae = [], []
        for t in range(trials):
            M, q, _, al = system(seed=7000 + t)
            fl1, fbox, fl2 = (lanes if lanes else (f_m, f_m, f_m))
            kap = snap(KAPPA * al, min(fl1, f_m))
            hi = snap(BOXHI * al, min(fbox, f_m))
            gam = snap(GAMMA, min(fl2, f_m))
            zr, _, _ = admm_float(M, q, mode, N, kappa=kap, box=(-hi, hi),
                                  gamma=gam, rho=RHO, max_iter=MAX_IT, eps=1e-9)
            zf = run_fixed(M, q, mode, f_m, fl1, fbox, fl2, kap, hi, gam)
            d2 = np.linalg.norm(zr) ** 2
            ne.append(np.linalg.norm(zf - zr) ** 2 / (d2 if d2 > 1e-12 else 1))
            ae.append(np.mean((zf - zr) ** 2))
        out[f_m] = (float(np.mean(ne)), float(np.mean(ae)))
        print(f"   {f_m:3d}   {out[f_m][0]:.3e}   {out[f_m][1]:.3e}")
    return out


if __name__ == "__main__":
    NAMES = {0: "L1", 1: "Box", 2: "L2"}
    print("MAIN DATAPATH SWEEP  (lanes pinned at derived 8/7/8)")
    pinned = {m: sweep(m, (8, 7, 8), f"{NAMES[m]}, lanes 8/7/8") for m in (0, 1, 2)}
    print("\n\nFULLY UNIFORM  (lanes tied to F_M)")
    unif = {m: sweep(m, None, f"{NAMES[m]}, lanes = F_M") for m in (0, 1, 2)}

    print("\n" + "=" * 62)
    print("Minimum F_M meeting each NMSE target:")
    for tgt in (1e-3, 1e-4, 1e-5):
        r1 = {m: next((f for f in range(6, 17) if pinned[m][f][0] <= tgt), None)
              for m in (0, 1, 2)}
        r2 = {m: next((f for f in range(6, 17) if unif[m][f][0] <= tgt), None)
              for m in (0, 1, 2)}
        print(f"  {tgt:7.0e}  lanes 8/7/8: L1={r1[0]} Box={r1[1]} L2={r1[2]}"
              f"   |  uniform: L1={r2[0]} Box={r2[1]} L2={r2[2]}")
