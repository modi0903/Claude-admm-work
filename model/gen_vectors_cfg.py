"""Golden vectors for an ARBITRARY lane configuration.

    python3 model/gen_vectors_cfg.py <F_MAIN> <F_L1> <F_BOX> <F_L2> <tag>

gen_vectors_fm.py only emits uniform lanes (tag `_unif`), and gen_vectors.py
only emits the single asymmetric configuration baked into fxp_admm.py
(F_BOX_ASYM=8, F_L2_ASYM=7 at F_MAIN=16). Neither covers `asym_derived`
(8/7/8 at F_MAIN=16) or `main9_asym` (9/8/9 at F_MAIN=9), so those builds
currently have NO valid golden vectors -- the committed `_asym` set belongs
to a different lane configuration and would falsely fail them.

Constants are derived per LANE, exactly as the RTL's q_narrow_const does from
the Q2.16 spec, so kappa lands on the L1 lane lattice, the box bound on the
Box lane lattice, gamma on the L2 lane lattice.

Self-check: with (16,16,16,16) this reproduces the committed *_unif vectors
and with (16,16,8,7) the committed *_asym vectors, bit for bit.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from main_sweep import run_fixed, fx, INT_BITS
from gen_vectors import build_system

if len(sys.argv) < 6:
    print(__doc__)
    sys.exit(1)

FM, FL1, FBOX, FL2 = (int(a) for a in sys.argv[1:5])
TAG = sys.argv[5]
WM = INT_BITS + FM
OUT = os.path.join(os.path.dirname(__file__), "..", "tb", "vectors")
os.makedirs(OUT, exist_ok=True)


def qnc(v, sh):                      # mirrors rtl q_narrow_const
    return v if sh <= 0 else (v + (1 << (sh - 1))) >> sh


# Q2.16 spec constants, narrowed to each lane's own width.
KAP = qnc(6554,  16 - FL1)  / float(1 << FL1)
HI  = qnc(65536, 16 - FBOX) / float(1 << FBOX)
GAM = qnc(43691, 16 - FL2)  / float(1 << FL2)
print(f"F_MAIN={FM} lanes {FL1}/{FBOX}/{FL2}  "
      f"kappa={KAP:.6f} box=±{HI:.6f} gamma={GAM:.6f}  tag=_{TAG}")


def hexs(v):
    m = (1 << WM) - 1
    return "\n".join(f"{x & m:0{(WM + 3) // 4}x}" for x in v) + "\n"


for mode, name in ((0, "l1"), (1, "box"), (2, "l2")):
    M, q, _ = build_system(seed=1000 + mode)
    z = run_fixed(M, q, mode, FM, FL1, FBOX, FL2, KAP, HI, GAM, iters=32)
    zi = [fx(e, FM, WM) for e in z]
    t = f"{name}_{TAG}"
    open(f"{OUT}/M_{t}.mem", "w").write(hexs([fx(v, FM, WM) for v in np.asarray(M).ravel()]))
    open(f"{OUT}/q_{t}.mem", "w").write(hexs([fx(v, FM, WM) for v in np.asarray(q)]))
    open(f"{OUT}/z_{t}.mem", "w").write(hexs(zi))
    print(f"  wrote {t}")
