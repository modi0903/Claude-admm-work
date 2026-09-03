"""
lattice_rule.py -- tests the prediction that fell out of Theorem 1's validation.

PREDICTION. L1's extra precision cost over Box is NOT active-set
misclassification (measured at zero). It is quantization of the threshold
kappa, which contributes (1-d)*dk^2 on top of the input round-off. Therefore:

  (1) placing kappa on the lane's quantization lattice should drive dk -> 0 and
      make L1 cost the same as Box at equal degenerate fraction d;
  (2) placing kappa maximally off-lattice (offset q/2) should cost exactly
      ONE bit: (q^2/12 + q^2/4)/(q^2/12) = 4x in MSE, and MSE ~ 2^(-2F), so a
      4x MSE penalty is one bit of wordlength, not two;
  (3) the effect must survive the full ADMM loop, i.e. F*_L1 must drop.

(3) is the one that matters. (1) and (2) are operator-level checks that tell us
whether a failure in (3) is the theory's fault or the loop's.

If this holds it is the first design rule the theory produces, and it is free:
snap the operator constants to the lattice at synthesis time.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import (ProxConfig, prox_l1, prox_box, admm_fixed, admm_float,
                      vec_fl, to_fx, to_fl, F_MAIN)
from experiments import system, N, RHO, MAX_IT


def snap_q16(val_q16, F):
    """Round a Q2.16 constant onto the lattice of a width-F lane, so the
    lane's narrowing cast is exact and the parameter error dk is zero."""
    step = 1 << (F_MAIN - F)
    return int(round(val_q16 / step) * step)


def offlattice_q16(val_q16, F):
    """Worst case: sit exactly half a lane-step off the lattice."""
    step = 1 << (F_MAIN - F)
    return snap_q16(val_q16, F) + step // 2


def harvest_v(trials=150, iters=40, gam=0.667):
    vs = []
    for t in range(trials):
        M, q, _, al = system(seed=41000 + t)
        z, u = np.zeros(N), np.zeros(N)
        for _ in range(iters):
            x = M @ (q + RHO * (z - u))
            v = x + u
            vs.append(v.copy())
            zn = gam * v
            u, z = u + x - zn, zn
    return np.concatenate(vs)


# ---------------------------------------------------------- operator level
def operator_test(F=8):
    print(f"\n=== (1)+(2) operator level, F={F} ===")
    v_raw = harvest_v()
    v_fx = np.array([to_fx(x) for x in v_raw])
    v_ref = np.array([to_fl(x) for x in v_fx])
    q = 2.0 ** (-F)
    base = q * q / 12.0

    print("  target kappa chosen to hit a range of degenerate fractions\n")
    print("   kappa_nom     d      MSE(on-lattice)  MSE(off-lattice)   ratio  "
          "  MSE(Box, same d)")
    for kn in (0.20, 0.35, 0.50, 0.70):
        k_on = snap_q16(to_fx(kn), F)
        k_off = offlattice_q16(to_fx(kn), F)

        res = {}
        for tag, kq in (("on", k_on), ("off", k_off)):
            kf = to_fl(kq)
            cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F, kappa_q16=kq)
            ze = np.sign(v_ref) * np.maximum(np.abs(v_ref) - kf, 0.0)
            zf = np.array([to_fl(prox_l1(int(x), cfg)) for x in v_fx])
            res[tag] = float(np.mean((zf - ze) ** 2))
            if tag == "on":
                d = float((np.abs(v_ref) <= kf).mean())

        # Box bound giving the SAME degenerate fraction, on-lattice
        hi = float(np.quantile(np.abs(v_ref), 1.0 - d))
        hq = snap_q16(to_fx(hi), F)
        hf = to_fl(hq)
        cfgb = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                          box_hi_q16=hq, box_lo_q16=-hq)
        zeb = np.clip(v_ref, -hf, hf)
        zfb = np.array([to_fl(prox_box(int(x), cfgb)) for x in v_fx])
        mse_box = float(np.mean((zfb - zeb) ** 2))

        print(f"  {kn:8.3f}  {d:7.4f}   {res['on']:13.4e}  {res['off']:15.4e}  "
              f"{res['off']/res['on']:7.2f}   {mse_box:14.4e}")
    print(f"\n  predicted off/on ratio = 4.00 (= 2 bits); "
          f"(1-d)*q^2/12 baseline at d=0 is {base:.4e}")


# ---------------------------------------------------------- full ADMM loop
def loop_test(target=1e-4, trials=40, kn=0.35):
    print(f"\n=== (3) full ADMM loop: does F* drop?  kappa_nom={kn}, "
          f"target NMSE {target:g} ===\n")
    print("   mode                       F*   ")
    out = {}
    for tag in ("L1 kappa on-lattice", "L1 kappa off-lattice", "Box on-lattice"):
        found = None
        for F in range(3, 15):
            accs = []
            for t in range(trials):
                M, q, _, al = system(seed=7000 + t)
                if tag.startswith("L1"):
                    kq = (snap_q16(to_fx(kn * al), F) if "on-" in tag
                          else offlattice_q16(to_fx(kn * al), F))
                    cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F, kappa_q16=kq)
                    mode, kf = 0, to_fl(kq)
                    zr, _, _ = admm_float(M, q, mode, N, kappa=kf, rho=RHO,
                                          max_iter=MAX_IT, eps=1e-9)
                else:
                    hq = snap_q16(to_fx(1.0 * al), F)
                    cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                                     box_hi_q16=hq, box_lo_q16=-hq)
                    mode = 1
                    zr, _, _ = admm_float(M, q, mode, N,
                                          box=(-to_fl(hq), to_fl(hq)), rho=RHO,
                                          max_iter=MAX_IT, eps=1e-9)
                zf = vec_fl(admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT)[0])
                dd = np.linalg.norm(zr) ** 2
                accs.append(np.linalg.norm(zf - zr) ** 2 / (dd if dd > 1e-12 else 1))
            if np.mean(accs) <= target:
                found = F
                break
        out[tag] = found
        print(f"   {tag:26s} {found}")
    a, b = out["L1 kappa on-lattice"], out["L1 kappa off-lattice"]
    c = out["Box on-lattice"]
    if a and b:
        print(f"\n   lattice alignment saves {b - a} bit(s) on the L1 lane")
    if a and c:
        print(f"   on-lattice L1 vs Box: {a} vs {c}")
    return out


if __name__ == "__main__":
    print("LATTICE RULE TEST")
    operator_test()
    loop_test()
