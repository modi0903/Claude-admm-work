"""
experiments.py -- the empirical evidence the manuscript is missing.

E1  Per-operator wordlength sweep  -> does W*_L1 > W*_Box >= W*_L2 actually hold?
E2  Convergence: K_uniform vs K_asym at matched accuracy.
E3  Uncoded BER vs SNR for the Box (detection) phase: float / uniform / asym.

Nothing here is asserted from theory. Every number is measured.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import (ProxConfig, admm_fixed, admm_float, vec_fl, F_MAIN,
                      SAT_COUNT, sat_reset, to_fx)

N, NR, RHO, MAX_IT = 8, 32, 1.0, 64
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


# Q2.16 spans [-2, 2). Measured peaks without scaling: |q| -> 2.81,
# |w| -> 3.80. Both clip. The fix is exact, not a compromise: the whole ADMM
# recursion is positively homogeneous, so scaling (q, kappa, box bounds) by a
# common alpha scales (x, z, u) by alpha and leaves the iterate trajectory
# identical. M is untouched. This is one scalar computed alongside M and q in
# the per-coherence-interval preprocessing step -- zero hardware cost. It is
# also what an AGC already does in a real receiver.
ALPHA_TARGET = 0.95


def system(seed, snr_db=12.0):
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((NR, N)) / np.sqrt(NR)
    s = rng.choice([-1.0, 1.0], N)
    p = np.linalg.norm(H @ s) ** 2 / NR
    y = H @ s + rng.standard_normal(NR) * np.sqrt(p / 10 ** (snr_db / 10))
    M = np.linalg.inv(H.T @ H + RHO * np.eye(N))
    q = H.T @ y
    alpha = min(1.0, ALPHA_TARGET / max(np.abs(q).max(), 1e-9))
    return M, q * alpha, s, alpha


def scaled_cfg(alpha, **kw):
    """Scale the problem-dependent constants by the same alpha."""
    return ProxConfig(kappa_q16=to_fx(0.10 * alpha),
                      box_hi_q16=to_fx(1.0 * alpha),
                      box_lo_q16=to_fx(-1.0 * alpha), **kw)


def ref(M, q, mode, cfg):
    z, _, _ = admm_float(M, q, mode, N, kappa=cfg.kappa_f, box=cfg.box_f,
                         gamma=cfg.gamma_f, rho=RHO, max_iter=MAX_IT, eps=1e-9)
    return z


# ---------------------------------------------------------------- E1: sweep
def e1(trials=60, target=1e-3):
    print("E1  per-operator minimum fractional wordlength (target NMSE "
          f"<= {target:g} vs float)\n")
    names = {0: "L1  soft-threshold", 1: "Box projection", 2: "L2  ridge"}
    curves, wstar = {}, {}
    sat_reset()
    for mode in (0, 1, 2):
        errs = []
        for f in range(2, 17):
            acc = []
            for t in range(trials):
                M, q, _, al = system(seed=7000 + t)
                cfg = scaled_cfg(al, f_l1=f, f_box=f, f_l2=f)
                zr = ref(M, q, mode, cfg)
                zf, _, _ = admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT)
                zf = vec_fl(zf)
                d = np.linalg.norm(zr) ** 2
                acc.append(np.linalg.norm(zf - zr) ** 2 / (d if d > 1e-12 else 1.0))
            errs.append(float(np.mean(acc)))
        curves[mode] = errs
        ok = [i + 2 for i, e in enumerate(errs) if e <= target]
        wstar[mode] = ok[0] if ok else None
        print(f"  {names[mode]:22s} F* = {wstar[mode]}  "
              f"(total width {wstar[mode] + 2 if wstar[mode] else '-'} bits)")
    print(f"\n  saturation events during sweep: {SAT_COUNT[0]} "
          f"({'clean' if SAT_COUNT[0] == 0 else 'RANGE PROBLEM'})")
    a, b, c = wstar[0], wstar[1], wstar[2]
    print(f"\n  ordering claim  W*_L1 > W*_Box >= W*_L2 : "
          f"{a} > {b} >= {c}  ->  {'HOLDS' if (a > b >= c) else 'DOES NOT HOLD'}")
    return {"curves": curves, "wstar": wstar}


# ---------------------------------------------------- E2: iteration counts
def e2(trials=200, eps=2e-3):
    print(f"\nE2  iterations to ||r||_inf,||s||_inf <= {eps:g}\n")
    out = {}
    for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
        for lbl in ("uniform", "asym"):
            ks = []
            for t in range(trials):
                M, q, _, al = system(seed=9000 + t)
                cfg = scaled_cfg(al, asymmetric=(lbl == "asym"))
                _, k, _ = admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT,
                                     eps_pri=eps, eps_dual=eps)
                ks.append(k)
            out[f"{nm}_{lbl}"] = (float(np.mean(ks)), int(np.max(ks)))
            print(f"  {nm:4s} {lbl:8s}  K_mean = {np.mean(ks):5.2f}   "
                  f"K_max = {np.max(ks)}")
    return out


# ------------------------------------------------------------- E3: BER
def e3(trials=400, snrs=(0, 2, 4, 6, 8, 10, 12, 14)):
    print("\nE3  uncoded BER, Box-constrained detection (BPSK, "
          f"{NR}x{N} real)\n")
    res = {"snr": list(snrs), "float": [], "uniform": [], "asym": [],
           "mmse": []}
    for snr in snrs:
        eF = eU = eA = eM = 0
        for t in range(trials):
            M, q, s, al = system(seed=11000 + t + 977 * snr, snr_db=snr)
            cfgU = scaled_cfg(al, asymmetric=False)
            cfgA = scaled_cfg(al, asymmetric=True)
            eM += int(np.sum(np.sign(M @ q) != s))
            eF += int(np.sum(np.sign(ref(M, q, 1, cfgU)) != s))
            zu, _, _ = admm_fixed(M, q, 1, N, cfgU, max_iter=32)
            za, _, _ = admm_fixed(M, q, 1, N, cfgA, max_iter=32)
            eU += int(np.sum(np.sign(vec_fl(zu)) != s))
            eA += int(np.sum(np.sign(vec_fl(za)) != s))
        tot = trials * N
        for k, v in (("mmse", eM), ("float", eF), ("uniform", eU), ("asym", eA)):
            res[k].append(v / tot)
        print(f"  SNR {snr:5.1f} dB   MMSE {eM/tot:.2e}   float {eF/tot:.2e}   "
              f"unif18 {eU/tot:.2e}   asym {eA/tot:.2e}")
    return res


if __name__ == "__main__":
    r = {"e1": e1(), "e2": e2(), "e3": e3()}
    with open(f"{OUT}/experiments.json", "w") as f:
        json.dump(r, f, indent=1, default=str)
    print(f"\nsaved -> {os.path.relpath(OUT)}/experiments.json")
