"""
derive_widths.py -- final lane widths, replacing the unjustified 18/10/9.

Operating parameters are the ones the architecture actually uses, with every
constant snapped to its lane's lattice (Appendix B.3). F* is reported under
both metrics at three targets so the choice is auditable.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import ProxConfig, admm_fixed, admm_float, vec_fl, to_fx, to_fl
from experiments import system, N, RHO, MAX_IT
from lattice_rule import snap_q16

TRIALS = 60
KAPPA, BOXHI, GAMMA = 0.10, 1.00, 0.667

def measure(mode, F):
    ae, ne, dfrac = [], [], []
    for t in range(TRIALS):
        M, q, _, al = system(seed=7000+t)
        kq = snap_q16(to_fx(KAPPA*al), F)
        hq = snap_q16(to_fx(BOXHI*al), F)
        gq = snap_q16(to_fx(GAMMA),    F)
        cfg = ProxConfig(f_l1=F, f_box=F, f_l2=F,
                         kappa_q16=kq, box_hi_q16=hq, box_lo_q16=-hq,
                         gamma_q16=gq)
        zr,_,_ = admm_float(M,q,mode,N,kappa=to_fl(kq),
                            box=(-to_fl(hq),to_fl(hq)), gamma=to_fl(gq),
                            rho=RHO, max_iter=MAX_IT, eps=1e-9)
        zf = vec_fl(admm_fixed(M,q,mode,N,cfg,max_iter=MAX_IT)[0])
        d2 = np.linalg.norm(zr)**2
        ae.append(np.mean((zf-zr)**2))
        ne.append(np.linalg.norm(zf-zr)**2/(d2 if d2>1e-12 else 1))
        v = zr
        dfrac.append(np.mean(np.abs(v) <= to_fl(kq)) if mode==0 else
                     np.mean(np.abs(v) >= to_fl(hq)*0.999) if mode==1 else 0.0)
    return float(np.mean(ae)), float(np.mean(ne)), float(np.mean(dfrac))

NAMES = {0:"L1  (sparse chan. est.)", 1:"Box (detect/precode)", 2:"L2  (interf. mitig.)"}
data = {m:{F:measure(m,F) for F in range(3,15)} for m in (0,1,2)}

print("degenerate fraction d at the operating point:")
for m in (0,1,2):
    print(f"   {NAMES[m]:26s} d = {data[m][10][2]:.3f}")

for label, idx, tgts in (("NMSE", 1, (1e-3,1e-4,1e-5)), ("abs MSE", 0, (1e-4,1e-5,1e-6))):
    print(f"\nF* under {label}:")
    for tg in tgts:
        row = {m: next((F for F in range(3,15) if data[m][F][idx] <= tg), None)
               for m in (0,1,2)}
        print(f"   {tg:8.0e}   L1={row[0]}  Box={row[1]}  L2={row[2]}")

print("\nRECOMMENDED (NMSE 1e-4, +1 bit design margin), total width = 2 + F:")
sel = {m: next((F for F in range(3,15) if data[m][F][1] <= 1e-4), None) for m in (0,1,2)}
for m in (0,1,2):
    print(f"   {NAMES[m]:26s} F* = {sel[m]}  ->  F = {sel[m]+1}, "
          f"total {sel[m]+3} bits")
