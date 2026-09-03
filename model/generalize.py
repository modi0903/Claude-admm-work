"""
generalize.py -- SPRINT 1, the experiment that decides the paper.

Everything measured so far is one Gaussian channel, one operating point, N=8.
A reviewer's first question is whether any of it holds elsewhere. Li et al.
(TRETS 2023) validated their SQNR model across three input signals; we need to
match or exceed that breadth.

THE TEST. Theorem 1 says the per-element error of a lane at fractional width F
is

    MSE  =  ( C_path  +  A_op ) * q^2/12 * G_loop ,      q = 2^-F

where A_op is operator-specific and computable from measurable quantities:

    A_L1  = (1 - d)                       constants on-lattice
    A_Box = (1 - d)
    A_L2  = gamma^2 + E[v^2] + 1          no degenerate set; the middle term is
                                          coefficient quantization, which the
                                          contraction does NOT attenuate

C_path (the operator-independent main-datapath contribution) and G_loop are
folded into ONE fitted constant. That is one free parameter predicting every
(ensemble x size x operator) cell.

FALSIFIER: if measured MSE does not track (C + A_op) with a single global C
across all cells, Theorem 1 does not generalise and the paper changes again.

The classical Oppenheim/Widrow model that FAM and Constantinides use is the
special case A_op = L^2, with no (1-d) term. We report both.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import _sat, q_narrow, q_widen

INT_BITS, ACC_INT = 2, 8
RHO, MAX_IT = 1.0, 48
KAPPA, BOXHI, GAMMA = 0.10, 1.00, 0.667
ALPHA_TARGET = 0.95
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


# ------------------------------------------------------------------ helpers
def fx(x, f, w):
    return _sat(int(np.floor(x * (1 << f) + 0.5)), w)


def fl(x, f):
    return x / float(1 << f)


def snap_lat(val, f):
    """Put a constant on the lane lattice (Appendix B.3)."""
    return round(val * (1 << f)) / float(1 << f)


def sadd(a, b, w, sub=False):
    return _sat(a - b if sub else a + b, w)


# ------------------------------------------------------------------ ensembles
def make_channel(kind, n, nr, rng):
    H = rng.standard_normal((nr, n)) / np.sqrt(nr)
    if kind == "gaussian":
        return H
    if kind == "illcond":
        U, s, Vt = np.linalg.svd(H, full_matrices=False)
        s = np.geomspace(s[0], s[0] / 50.0, len(s))
        return U @ np.diag(s) @ Vt
    if kind == "correlated":
        idx = np.arange(n)
        R = 0.9 ** np.abs(idx[:, None] - idx[None, :])       # exponential corr
        return H @ np.linalg.cholesky(R).T
    if kind == "uniform":
        return (rng.uniform(-1, 1, (nr, n)) * np.sqrt(3)) / np.sqrt(nr)
    raise ValueError(kind)


def system(kind, n, seed, snr_db=12.0):
    rng = np.random.default_rng(seed)
    nr = 4 * n
    H = make_channel(kind, n, nr, rng)
    s = rng.choice([-1.0, 1.0], n)
    p = np.linalg.norm(H @ s) ** 2 / nr
    y = H @ s + rng.standard_normal(nr) * np.sqrt(p / 10 ** (snr_db / 10))
    M = np.linalg.inv(H.T @ H + RHO * np.eye(n))
    q = H.T @ y
    a = min(1.0, ALPHA_TARGET / max(np.abs(q).max(), 1e-9))
    return M, q * a, a


# ------------------------------------------------------------------ solvers
def admm_float(M, q, mode, n, kap, hi, gam, iters=MAX_IT):
    z, u = np.zeros(n), np.zeros(n)
    vs = []
    for _ in range(iters):
        x = M @ (q + RHO * (z - u))
        v = x + u
        vs.append(v.copy())
        if mode == 0:
            zn = np.sign(v) * np.maximum(np.abs(v) - kap, 0.0)
        elif mode == 1:
            zn = np.clip(v, -hi, hi)
        else:
            zn = gam * v
        u, z = u + x - zn, zn
    return z, np.concatenate(vs)


def admm_fixed(M, q, mode, n, F, kap, hi, gam, iters=MAX_IT):
    W = INT_BITS + F
    f_acc, w_acc = 2 * F, ACC_INT + 2 * F
    Mf = [fx(v, F, W) for v in np.asarray(M).ravel()]
    qf = [fx(v, F, W) for v in np.asarray(q).ravel()]
    kf, hf, gf = fx(kap, F, W), fx(hi, F, W), fx(gam, F, W)
    z, u = [0] * n, [0] * n
    for _ in range(iters):
        w = [sadd(qf[i], sadd(z[i], u[i], W, sub=True), W) for i in range(n)]
        x = []
        for i in range(n):
            acc = sum(Mf[i * n + j] * w[j] for j in range(n))
            assert abs(acc) < (1 << (w_acc - 1)), "accumulator overflow"
            x.append(q_narrow(acc, f_acc, W, F))
        v = [sadd(x[i], u[i], W) for i in range(n)]
        if mode == 0:
            zn = [_sat((lambda m: -m if v[i] < 0 else m)(max(abs(v[i]) - kf, 0)), W)
                  for i in range(n)]
        elif mode == 1:
            zn = [min(max(v[i], -hf), hf) for i in range(n)]
        else:
            zn = [q_narrow(v[i] * gf, 2 * F, W, F) for i in range(n)]
        u = [sadd(u[i], sadd(x[i], zn[i], W, sub=True), W) for i in range(n)]
        z = zn
    return np.array([fl(e, F) for e in z])


# ------------------------------------------------------------------ the sweep
def cell(kind, n, mode, F, trials, seed0=7000):
    mses, ds, ev2s = [], [], []
    for t in range(trials):
        M, q, a = system(kind, n, seed0 + t)
        kap, hi, gam = (snap_lat(KAPPA * a, F), snap_lat(BOXHI * a, F),
                        snap_lat(GAMMA, F))
        zr, vs = admm_float(M, q, mode, n, kap, hi, gam)
        zf = admm_fixed(M, q, mode, n, F, kap, hi, gam)
        mses.append(np.mean((zf - zr) ** 2))
        if mode == 0:
            ds.append(np.mean(np.abs(vs) <= kap))
        elif mode == 1:
            ds.append(np.mean(np.abs(vs) >= hi))
        else:
            ds.append(0.0)
        ev2s.append(np.mean(vs ** 2))
    return float(np.mean(mses)), float(np.mean(ds)), float(np.mean(ev2s))


def A_op(mode, d, ev2, gam=GAMMA):
    if mode in (0, 1):
        return 1.0 - d
    return gam * gam + ev2 + 1.0


if __name__ == "__main__":
    ENS = ["gaussian", "illcond", "correlated", "uniform"]
    SIZES = [8, 16]
    MODES = [(0, "L1"), (1, "Box"), (2, "L2")]
    F_TEST, TRIALS = 10, 25
    q2_12 = (2.0 ** -F_TEST) ** 2 / 12.0

    print(f"SPRINT 1 — generalisation.  F={F_TEST}, {TRIALS} trials/cell, "
          f"{len(ENS)*len(SIZES)*len(MODES)} cells\n")
    print(f"{'ensemble':12s} {'N':>3s} {'op':4s} {'d':>7s} {'E[v^2]':>8s} "
          f"{'A_op':>7s} {'MSE_meas':>11s}")
    rows = []
    for kind in ENS:
        for n in SIZES:
            for mode, nm in MODES:
                mse, d, ev2 = cell(kind, n, mode, F_TEST, TRIALS)
                A = A_op(mode, d, ev2)
                rows.append(dict(ens=kind, n=n, mode=mode, op=nm, mse=mse,
                                 d=d, ev2=ev2, A=A))
                print(f"{kind:12s} {n:3d} {nm:4s} {d:7.4f} {ev2:8.4f} "
                      f"{A:7.3f} {mse:11.4e}")

    # ---- single-parameter fit:  MSE = K * (C + A_op) * q^2/12 --------------
    y = np.array([r["mse"] for r in rows]) / q2_12
    A = np.array([r["A"] for r in rows])

    def fit(C):
        K = float(np.sum(y * (C + A)) / np.sum((C + A) ** 2))
        pred = K * (C + A)
        return K, pred, float(np.mean(np.abs(np.log2(pred / y)) / 2))

    Cs = np.geomspace(0.05, 500, 400)
    best = min(((fit(c)[2], c) for c in Cs))
    C_hat = best[1]
    K_hat, pred, err_bits = fit(C_hat)

    # classical Oppenheim/Widrow: A = L^2, no (1-d) term
    A_cls = np.array([1.0 if r["mode"] in (0, 1) else GAMMA ** 2 for r in rows])

    def fit_cls(C):
        K = float(np.sum(y * (C + A_cls)) / np.sum((C + A_cls) ** 2))
        return K, K * (C + A_cls), float(np.mean(np.abs(np.log2(K * (C + A_cls) / y)) / 2))
    best_c = min(((fit_cls(c)[2], c) for c in Cs))
    _, pred_c, err_c = fit_cls(best_c[1])

    print(f"\nfitted  C = {C_hat:.3f}   K = {K_hat:.3f}   (one free parameter)")
    print(f"\n{'ensemble':12s} {'N':>3s} {'op':4s} {'meas/q2_12':>11s} "
          f"{'T1 pred':>10s} {'err(bits)':>10s} {'classical':>10s} {'err(bits)':>10s}")
    for i, r in enumerate(rows):
        eb = abs(np.log2(pred[i] / y[i])) / 2
        ec = abs(np.log2(pred_c[i] / y[i])) / 2
        print(f"{r['ens']:12s} {r['n']:3d} {r['op']:4s} {y[i]:11.3f} "
              f"{pred[i]:10.3f} {eb:10.3f} {pred_c[i]:10.3f} {ec:10.3f}")

    print(f"\n{'='*72}")
    print(f"  Theorem 1 model   : mean |error| = {err_bits:.3f} bits   "
          f"max = {max(abs(np.log2(pred[i]/y[i]))/2 for i in range(len(rows))):.3f} bits")
    print(f"  classical model   : mean |error| = {err_c:.3f} bits   "
          f"max = {max(abs(np.log2(pred_c[i]/y[i]))/2 for i in range(len(rows))):.3f} bits")
    ok = err_bits <= 0.5
    print(f"\n  SUCCESS CRITERION (<= 0.5 bit mean): "
          f"{'PASS' if ok else 'FAIL'}")
    json.dump({"rows": rows, "C": C_hat, "K": K_hat,
               "err_bits_T1": err_bits, "err_bits_classical": err_c},
              open(f"{OUT}/generalize.json", "w"), indent=1)
    print(f"  saved -> {os.path.relpath(OUT)}/generalize.json")
