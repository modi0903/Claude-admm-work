"""
metric_check.py -- resolves the open discrepancy in THEORY_PLAN Appendix B.4.

On-lattice L1 needed 7 bits vs Box's 6 in the closed loop, despite identical
operator-level error at matched degenerate fraction. Hypothesis: NMSE
normalises by ||z*||^2, and soft-thresholding shrinks ||z*||, so the same
ABSOLUTE error reports as a larger RELATIVE error.

Test: rerun F* under an absolute criterion (mean squared error per component,
unnormalised) alongside NMSE, and measure ||z*|| for each operator.
If the gap closes under the absolute metric, it was a metric artifact.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import ProxConfig, admm_fixed, admm_float, vec_fl, to_fx, to_fl
from experiments import system, N, RHO, MAX_IT
from lattice_rule import snap_q16, offlattice_q16

TRIALS, KN = 40, 0.35

def measure(tag, F):
    """Returns (mean squared abs error, mean NMSE, mean ||z*||)."""
    ae, ne, nz = [], [], []
    for t in range(TRIALS):
        M, q, _, al = system(seed=7000 + t)
        if tag.startswith("L1"):
            kq = (snap_q16(to_fx(KN*al), F) if "on-" in tag
                  else offlattice_q16(to_fx(KN*al), F))
            cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F, kappa_q16=kq)
            mode = 0
            zr,_,_ = admm_float(M,q,mode,N,kappa=to_fl(kq),rho=RHO,
                                max_iter=MAX_IT,eps=1e-9)
        else:
            hq = snap_q16(to_fx(1.0*al), F)
            cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                             box_hi_q16=hq, box_lo_q16=-hq)
            mode = 1
            zr,_,_ = admm_float(M,q,mode,N,box=(-to_fl(hq),to_fl(hq)),rho=RHO,
                                max_iter=MAX_IT,eps=1e-9)
        zf = vec_fl(admm_fixed(M,q,mode,N,cfg,max_iter=MAX_IT)[0])
        d2 = np.linalg.norm(zr)**2
        ae.append(np.mean((zf-zr)**2))
        ne.append(np.linalg.norm(zf-zr)**2/(d2 if d2>1e-12 else 1))
        nz.append(np.linalg.norm(zr))
    return float(np.mean(ae)), float(np.mean(ne)), float(np.mean(nz))

TAGS = ["L1 kappa on-lattice", "L1 kappa off-lattice", "Box on-lattice"]
data = {t: {F: measure(t, F) for F in range(3, 13)} for t in TAGS}

print("mean ||z*||  (shrinkage check):")
for t in TAGS:
    print(f"   {t:24s} {data[t][10][2]:.4f}")

for name, idx, targets in (("NMSE (relative)", 1, (1e-3,1e-4,1e-5)),
                           ("MSE  (absolute)", 0, (1e-4,1e-5,1e-6))):
    print(f"\nF* under {name}:")
    print("   target      " + "".join(f"{t:>24s}" for t in TAGS))
    for tg in targets:
        row = []
        for t in TAGS:
            f = next((F for F in range(3,13) if data[t][F][idx] <= tg), None)
            row.append(str(f))
        print(f"   {tg:9.0e}   " + "".join(f"{r:>24s}" for r in row))
