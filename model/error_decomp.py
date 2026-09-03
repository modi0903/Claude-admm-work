"""
error_decomp.py -- FALSIFIER for Theorem 1.

Theorem 1 claims that for a proximal operator P_theta evaluated at fractional
wordlength W (step q = 2^-W), partitioning the input into the degenerate set
D (where dP/dv = 0, so the operator annihilates the input perturbation) and its
complement:

    E||e||^2  =  (|D^c|/n) * [ L^2 * q^2/12  +  (theta quantization on D^c) ]
              +  (|D|/n)   * [ theta quantization on D ]

The standard quantization model assumes EVERY element contributes L^2 q^2/12.
If Theorem 1 is right, the standard model overestimates by roughly 1/(1-d)
where d = |D|/n, and that gap is the entire contribution of the paper.

This script measures the operator in isolation (not through the ADMM loop) on
a realistic v-distribution harvested from actual float ADMM runs.

Reference convention: the lane receives v already quantized to Q2.16. To
isolate the LANE's contribution, the exact reference is P_float applied to that
same Q2.16 value with EXACT (unquantized) parameters. Parameter quantization
therefore shows up as lane error, which is what we want to measure.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import (ProxConfig, prox_l1, prox_box, prox_l2, to_fx, to_fl,
                      F_MAIN, INT_BITS)
from experiments import system, N, RHO

MODES = {0: ("L1  soft-threshold", prox_l1),
         1: ("Box projection", prox_box),
         2: ("L2  ridge scaling", prox_l2)}


def harvest_v(mode, alpha_cfg, trials=120, iters=40):
    """Realistic distribution of v = x + u, from float ADMM."""
    vs = []
    for t in range(trials):
        M, q, _, al = system(seed=31000 + t)
        kap, box, gam = 0.10 * al, (-1.0 * al, 1.0 * al), 0.667
        z = np.zeros(N)
        u = np.zeros(N)
        for k in range(iters):
            x = M @ (q + RHO * (z - u))
            v = x + u
            vs.append(v.copy())
            if mode == 0:
                zn = np.sign(v) * np.maximum(np.abs(v) - kap, 0.0)
            elif mode == 1:
                zn = np.clip(v, box[0], box[1])
            else:
                zn = gam * v
            u = u + x - zn
            z = zn
    return np.concatenate(vs), al


def exact_prox(mode, v, kap, box, gam):
    if mode == 0:
        return np.sign(v) * np.maximum(np.abs(v) - kap, 0.0)
    if mode == 1:
        return np.clip(v, box[0], box[1])
    return gam * v


def degenerate_mask(mode, v, kap, box):
    """D = {i : dP/dv_i = 0}."""
    if mode == 0:
        return np.abs(v) <= kap          # soft-threshold zeroes these
    if mode == 1:
        return (v >= box[1]) | (v <= box[0])   # clipped
    return np.zeros_like(v, dtype=bool)  # L2 has no degenerate set


def run(mode, trials=120):
    name, prox_fn = MODES[mode]
    v_raw, alpha = harvest_v(mode, None, trials=trials)

    # exact parameter values, as specified in Q2.16
    KAP_Q, HI_Q, LO_Q, GAM_Q = (to_fx(0.10 * alpha), to_fx(1.0 * alpha),
                                to_fx(-1.0 * alpha), 43691)
    kap, box, gam = to_fl(KAP_Q), (to_fl(LO_Q), to_fl(HI_Q)), to_fl(GAM_Q)

    # the lane receives v already at Q2.16
    v_fx = np.array([to_fx(x) for x in v_raw])
    v_ref = np.array([to_fl(x) for x in v_fx])

    z_exact = exact_prox(mode, v_ref, kap, box, gam)
    D = degenerate_mask(mode, v_ref, kap, box)
    d = D.mean()

    print(f"\n=== {name} ===")
    print(f"  samples = {len(v_ref)}   degenerate fraction d = |D|/n = {d:.4f}")
    print()
    print("   F    MSE_total    MSE_on_D   MSE_on_Dc    naive q^2/12  "
          "naive/meas   pred_T1   T1/meas")
    rows = []
    for F in range(4, 15):
        cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                         kappa_q16=KAP_Q, box_hi_q16=HI_Q,
                         box_lo_q16=LO_Q, gamma_q16=GAM_Q)
        z_fx = np.array([to_fl(prox_fn(int(x), cfg)) for x in v_fx])
        e = z_fx - z_exact
        mse = float(np.mean(e ** 2))
        mse_D = float(np.mean(e[D] ** 2)) if D.any() else 0.0
        mse_Dc = float(np.mean(e[~D] ** 2)) if (~D).any() else 0.0

        q = 2.0 ** (-F)
        L = gam if mode == 2 else 1.0
        naive = (L ** 2) * q * q / 12.0          # every element contributes

        # Theorem 1 prediction
        # NOTE: cfg.kappa / box_hi / gamma are stored in Q(F), NOT Q2.16.
        # Converting them with the default F_MAIN scale is a 2^(16-F) error and
        # was what made the first run of this script disagree by 10^5.
        if mode == 0:      # L1: zero error on D; kappa quantization on D^c
            dk = to_fl(cfg.kappa, F) - kap
            pred = (1 - d) * (q * q / 12.0 + dk * dk)
        elif mode == 1:    # Box: v round-off on D^c; bound quantization on D
            dh = to_fl(cfg.box_hi, F) - box[1]
            pred = (1 - d) * (q * q / 12.0) + d * (dh * dh)
        else:              # L2: no D. gamma-attenuated input noise + coeff error
            dg = to_fl(cfg.gamma, F) - gam
            Ev2 = float(np.mean(v_ref ** 2))
            pred = (gam ** 2) * q * q / 12.0 + Ev2 * dg * dg + q * q / 12.0

        rows.append((F, mse, mse_D, mse_Dc, naive, naive / mse if mse > 0 else 0,
                     pred, pred / mse if mse > 0 else 0))
        print(f"  {F:2d}  {mse:11.3e} {mse_D:11.3e} {mse_Dc:11.3e}  "
              f"{naive:11.3e}  {naive/mse if mse>0 else 0:9.2f}  "
              f"{pred:9.3e}  {pred/mse if mse>0 else 0:7.2f}")
    return d, rows


if __name__ == "__main__":
    print("THEOREM 1 FALSIFIER")
    print("Key test: does MSE_on_D collapse (annihilation), and does the naive")
    print("model overestimate by ~1/(1-d) while the T1 prediction tracks ~1.0?")
    out = {}
    for m in (0, 1, 2):
        out[m] = run(m)
    print("\n" + "=" * 72)
    for m in (0, 1, 2):
        d, rows = out[m]
        mid = [r for r in rows if 6 <= r[0] <= 12]
        nr = np.mean([r[5] for r in mid])
        tr = np.mean([r[7] for r in mid])
        print(f"  {MODES[m][0]:22s} d={d:.3f}   naive/meas={nr:6.2f}   "
              f"1/(1-d)={1/(1-d) if d < 1 else float('inf'):6.2f}   "
              f"T1/meas={tr:5.2f}")
