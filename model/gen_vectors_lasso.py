"""
gen_vectors_lasso.py -- golden vectors for LASSO on the EXISTING RTL (P-L4).

    python model/gen_vectors_lasso.py <F_MAIN>       # writes *_l1_lasso{0,1,2}.mem

The RTL fixes kappa at synthesis (KAPPA_Q16 = 6554, i.e. 0.1 in Q2.16). A LASSO
instance with threshold lam/rho is mapped onto it by scaling q so that the
scaled threshold is exactly 0.1: by homogeneity (Lemma 1) the scaled problem's
solution is alpha times the original's, same support, same iterates up to
scale. So the SAME bitstream solves LASSO -- only the ROM changes.

Three instances, chosen to span the conditioning seen in lasso.py:
    lasso0  m=32  (well-determined)      ||M||2 ~ 0.74
    lasso1  m=16                          ||M||2 ~ 0.87
    lasso2  m=8   (square, ill-posed)     ||M||2 ~ 0.99
All at lam = 0.3 * lam_max, which keeps max|q| = 1/3 after scaling -- inside
the rho-aware range bound (1+rho)*max|q| < 2.

Golden z comes from main_sweep.run_fixed, the bit-exact model the RTL is
regression-tested against, with the constant narrowed from the Q2.16 spec to
the lane width exactly as the RTL's q_narrow_const does.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from main_sweep import run_fixed, fx, INT_BITS
from lasso import N, RHO

FM = int(sys.argv[1]) if len(sys.argv) > 1 else 16
WM = INT_BITS + FM
OUT = os.path.join(os.path.dirname(__file__), "..", "tb", "vectors")
LAM_FRAC, KAPPA_SPEC = 0.3, 6554            # RTL KAPPA_Q16


def qnc(v, sh):                              # mirrors rtl q_narrow_const
    return v if sh <= 0 else (v + (1 << (sh - 1))) >> sh


def hexs(v):
    m = (1 << WM) - 1
    return "\n".join(f"{x & m:0{(WM + 3) // 4}x}" for x in v) + "\n"


KAP = qnc(KAPPA_SPEC, 16 - FM) / float(1 << FM)     # kappa as the lane holds it
HI = qnc(65536, 16 - FM) / float(1 << FM)
GAM = qnc(43691, 16 - FM) / float(1 << FM)

print(f"F_MAIN={FM}  W={WM}  kappa(lane)={KAP:.6f}  lam={LAM_FRAC}*lam_max")
for i, (m, seed) in enumerate(((32, 5100), (16, 5101), (8, 5102))):
    rng = np.random.default_rng(seed)
    A = rng.standard_normal((m, N)) / np.sqrt(m)
    x0 = np.zeros(N)
    sup = rng.choice(N, 2, replace=False)
    x0[sup] = rng.choice([-1.0, 1.0], 2) * rng.uniform(0.5, 1.5, 2)
    y = A @ x0
    b = y + rng.standard_normal(m) * np.sqrt(np.mean(y ** 2) / 100.0)
    M = np.linalg.inv(A.T @ A + RHO * np.eye(N))
    q = A.T @ b
    # scale so that the threshold lam/rho lands exactly on the RTL's kappa
    alpha = (KAPPA_SPEC / 65536.0) * RHO / (LAM_FRAC * np.max(np.abs(q)))
    q = q * alpha
    assert (1 + RHO) * np.abs(q).max() < 2.0 and np.abs(M).max() < 2.0
    z = run_fixed(M, q, 0, FM, FM, FM, FM, KAP, HI, GAM, iters=32)
    zi = [fx(e, FM, WM) for e in z]
    tag = f"l1_lasso{i}"
    open(f"{OUT}/M_{tag}.mem", "w").write(hexs([fx(v, FM, WM) for v in M.ravel()]))
    open(f"{OUT}/q_{tag}.mem", "w").write(hexs([fx(v, FM, WM) for v in q]))
    open(f"{OUT}/z_{tag}.mem", "w").write(hexs(zi))
    nz = int(np.sum(np.array(zi) != 0))
    print(f"  wrote {tag}: m={m}  ||M||2={np.linalg.norm(M,2):.3f}  "
          f"nonzeros={nz}/{N}  true support={sorted(sup.tolist())}  "
          f"found={[j for j in range(N) if zi[j] != 0]}")
