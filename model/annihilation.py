"""
annihilation.py -- the decisive test of Theorem 1's central mechanism.

Claim: on the degenerate set D (where dP/dv = 0) the operator ANNIHILATES the
input perturbation exactly, so effective noise power scales with (1-d) where
d = |D|/n, instead of the standard model's flat q^2/12 per element.

Previous run couldn't exercise this: L1 had d = 0 (kappa too small relative to
the signal) and Box's annihilation was masked by quantization of the bound
itself. Here we sweep the operator PARAMETER so d ranges over [0, 1], and we
choose parameters that are EXACTLY representable at the test wordlength, which
zeroes the theta term and isolates annihilation.

That exact-representability requirement is itself a design rule worth stating:
a Box bound (or L1 threshold) that is not a multiple of the lane's quantization
step contributes a constant error on every degenerate element, cancelling the
benefit of degeneracy. Pick bounds on the lattice.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import ProxConfig, prox_l1, prox_box, to_fx, to_fl
from experiments import system, N, RHO

F_TEST = 8


def harvest_v(trials=150, iters=40, gam=0.667):
    """v = x + u from float ADMM. Operator-independent sample of the input
    distribution; using the L2 (linear) run avoids biasing v toward either
    operator's degenerate region."""
    vs = []
    for t in range(trials):
        M, q, _, al = system(seed=41000 + t)
        z = np.zeros(N)
        u = np.zeros(N)
        for _ in range(iters):
            x = M @ (q + RHO * (z - u))
            v = x + u
            vs.append(v.copy())
            zn = gam * v
            u = u + x - zn
            z = zn
    return np.concatenate(vs)


def on_lattice(val, F):
    """Snap a parameter to the lane's representable lattice."""
    return round(val * (1 << F)) / float(1 << F)


def sweep(mode, params, v_ref, v_fx, F=F_TEST):
    q = 2.0 ** (-F)
    base = q * q / 12.0
    label = "L1 threshold kappa" if mode == 0 else "Box bound hi"
    print(f"\n=== {'L1 soft-threshold' if mode==0 else 'Box projection'} "
          f"— sweeping {label} at F={F} ===")
    print(f"  standard model predicts a flat {base:.4e} regardless of d\n")
    print("   param      d=|D|/n   MSE_meas     (1-d)*q^2/12   T1/meas   "
          "naive/meas")
    rows = []
    for p in params:
        p = on_lattice(p, F)
        if mode == 0:
            cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F, kappa_q16=to_fx(p))
            D = np.abs(v_ref) <= p
            z_exact = np.sign(v_ref) * np.maximum(np.abs(v_ref) - p, 0.0)
            z_fx = np.array([to_fl(prox_l1(int(x), cfg)) for x in v_fx])
        else:
            cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                             box_hi_q16=to_fx(p), box_lo_q16=to_fx(-p))
            D = (v_ref >= p) | (v_ref <= -p)
            z_exact = np.clip(v_ref, -p, p)
            z_fx = np.array([to_fl(prox_box(int(x), cfg)) for x in v_fx])

        d = float(D.mean())
        mse = float(np.mean((z_fx - z_exact) ** 2))
        pred = (1 - d) * base
        rows.append((p, d, mse, pred))
        print(f"  {p:8.4f}   {d:8.4f}  {mse:11.4e}  {pred:12.4e}   "
              f"{pred/mse if mse>0 else float('nan'):7.3f}   "
              f"{base/mse if mse>0 else float('nan'):8.3f}")
    return rows


if __name__ == "__main__":
    print("ANNIHILATION TEST — does effective noise power scale with (1-d)?")
    v_raw = harvest_v()
    v_fx = np.array([to_fx(x) for x in v_raw])
    v_ref = np.array([to_fl(x) for x in v_fx])
    print(f"\nharvested {len(v_ref)} samples of v = x+u   "
          f"|v|: mean {np.mean(np.abs(v_ref)):.3f}  max {np.max(np.abs(v_ref)):.3f}")

    r1 = sweep(0, [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.4], v_ref, v_fx)
    r2 = sweep(1, [1.4, 1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.05, 0.02], v_ref, v_fx)

    print("\n" + "=" * 72)
    for nm, r in (("L1", r1), ("Box", r2)):
        rr = [x for x in r if 0.05 < x[1] < 0.95]
        if not rr:
            print(f"  {nm}: no usable d range")
            continue
        t1 = np.mean([x[3] / x[2] for x in rr])
        nv = np.mean([(2.0 ** (-F_TEST)) ** 2 / 12.0 / x[2] for x in rr])
        dlo, dhi = min(x[1] for x in rr), max(x[1] for x in rr)
        print(f"  {nm:4s} over d in [{dlo:.2f},{dhi:.2f}]:  "
              f"T1/meas = {t1:.3f}   standard/meas = {nv:.3f}")
    print("\nT1 near 1.0 across a wide d range, standard model drifting with d,")
    print("is the signature the theorem predicts.")
