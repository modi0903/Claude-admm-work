"""
range_check.py -- Proposition 1 (range feasibility), measured.

M = (H'H + rho I)^-1 has |M_ij| <= 1/rho, approached as H'H becomes singular,
so Q2.F weights (range [-2, 2)) are guaranteed representable only for
rho > 1/2. The proposition was registered before measurement; the original
measurement survived only as prose (THEORY_PLAN.md: 2.116 at rho=0.125,
1.117 at rho=0.5). This script reproduces it on the detection workload's own
channel generator (experiments.system: 32x8 real Gaussian, 600 draws), and on
an underdetermined generator where H'H is singular (m < N), where the bound
is approached.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from experiments import NR, N

RHOS = (0.125, 0.25, 0.5, 1.0)


def H_detect(seed):
    rng = np.random.default_rng(seed)          # same first draw as experiments.system
    return rng.standard_normal((NR, N)) / np.sqrt(NR)


def H_under(seed, m=6):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((m, N)) / np.sqrt(m)


def main():
    out = {}
    print(f"{'rho':>6s} {'1/rho':>6s} | {'max|M| detection 32x8':>22s} | {'max|M| m=6 (singular)':>22s} | Q2.F?")
    for rho in RHOS:
        md = max(np.abs(np.linalg.inv(H_detect(s).T @ H_detect(s) + rho * np.eye(N))).max() for s in range(600))
        mu = max(np.abs(np.linalg.inv(H_under(s).T @ H_under(s) + rho * np.eye(N))).max() for s in range(600))
        ok = mu < 2.0
        out[str(rho)] = dict(detect=float(md), under=float(mu), bound=1 / rho)
        print(f"{rho:6.3f} {1/rho:6.2f} | {md:22.3f} | {mu:22.3f} | {'yes' if ok else 'NO -- exceeds [-2,2)'}")
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "results", "range_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
