"""Golden vectors at an arbitrary main-datapath width F_MAIN (uniform lanes).
   usage: python3 model/gen_vectors_fm.py <F_MAIN>"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from main_sweep import run_fixed, fx, INT_BITS
from experiments import RHO
from gen_vectors import build_system, N

FM = int(sys.argv[1]) if len(sys.argv) > 1 else 16
WM = INT_BITS + FM
OUT = os.path.join(os.path.dirname(__file__), "..", "tb", "vectors")

def qnc(v, sh):                      # mirrors rtl q_narrow_const
    return v if sh <= 0 else (v + (1 << (sh-1))) >> sh

# exactly what the RTL derives from the Q2.16 spec at this lane width
KAP = qnc(6554,  16-FM) / float(1 << FM)
HI  = qnc(65536, 16-FM) / float(1 << FM)
GAM = qnc(43691, 16-FM) / float(1 << FM)
print(f"F_MAIN={FM}  kappa={KAP:.6f}  box=±{HI:.6f}  gamma={GAM:.6f}")

def hexs(v):
    m = (1 << WM) - 1
    return "\n".join(f"{x & m:0{(WM+3)//4}x}" for x in v) + "\n"

for mode, name in ((0,"l1"),(1,"box"),(2,"l2")):
    M, q, _ = build_system(seed=1000+mode)
    z = run_fixed(M, q, mode, FM, FM, FM, FM, KAP, HI, GAM, iters=32)
    zi = [fx(e, FM, WM) for e in z]
    tag = f"{name}_unif"
    open(f"{OUT}/M_{tag}.mem","w").write(hexs([fx(v,FM,WM) for v in np.asarray(M).ravel()]))
    open(f"{OUT}/q_{tag}.mem","w").write(hexs([fx(v,FM,WM) for v in np.asarray(q)]))
    open(f"{OUT}/z_{tag}.mem","w").write(hexs(zi))
    print(f"  wrote {tag}")
