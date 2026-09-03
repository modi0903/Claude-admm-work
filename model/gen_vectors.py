"""Generate .mem stimulus + golden responses for tb_admm_top.v."""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import (ProxConfig, admm_fixed, vec_fx, to_fx, W_MAIN)

OUT = os.path.join(os.path.dirname(__file__), "..", "tb", "vectors")
os.makedirs(OUT, exist_ok=True)

N = 8
NR = 32            # BS antennas -- affects only M and q, NOT the array size
RHO = 1.0
RHO_SHIFT = 0
SNR_DB = 12.0
MAX_ITER = 32


def hexs(v):
    m = (1 << W_MAIN) - 1
    return "\n".join(f"{x & m:0{(W_MAIN + 3) // 4}x}" for x in v) + "\n"


def build_system(seed):
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((NR, N)) / np.sqrt(NR)
    s = rng.choice([-1.0, 1.0], N)
    sig = np.linalg.norm(H @ s) ** 2 / NR
    y = H @ s + rng.standard_normal(NR) * np.sqrt(sig / (10 ** (SNR_DB / 10)))
    M = np.linalg.inv(H.T @ H + RHO * np.eye(N))
    q = H.T @ y
    # M and q must NOT be rescaled: M = (H'H + rho I)^-1 exactly, or the
    # x-update is no longer the ADMM x-update and the iteration is not the
    # algorithm we are analysing. With rho = 1 the eigenvalues of M are
    # bounded by 1/rho, so M already fits Q2.16 by construction.
    assert np.abs(M).max() < 2.0, f"M out of Q2.16 range: {np.abs(M).max():.3f}"
    assert np.abs(q).max() < 2.0, f"q out of Q2.16 range: {np.abs(q).max():.3f}"
    return M, q, s


def main():
    cases = []
    for mode, name in ((0, "l1"), (1, "box"), (2, "l2")):
        for asym in (0, 1):
            M, q, s = build_system(seed=1000 + mode)
            cfg = ProxConfig(asymmetric=bool(asym))
            z, it, _ = admm_fixed(M, q, mode, N, cfg,
                                  rho_shift=RHO_SHIFT, max_iter=MAX_ITER)
            tag = f"{name}_{'asym' if asym else 'unif'}"
            open(f"{OUT}/M_{tag}.mem", "w").write(hexs(vec_fx(M.ravel())))
            open(f"{OUT}/q_{tag}.mem", "w").write(hexs(vec_fx(q)))
            open(f"{OUT}/z_{tag}.mem", "w").write(hexs(z))
            cases.append((tag, mode, asym, it))
            print(f"{tag:12s} mode={mode} asym={asym} iters={it}")
    with open(f"{OUT}/manifest.txt", "w") as f:
        for tag, mode, asym, it in cases:
            f.write(f"{tag} {mode} {asym} {it}\n")
    print(f"\nwrote {len(cases)*3} files to {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
