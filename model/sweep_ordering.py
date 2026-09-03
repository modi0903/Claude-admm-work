"""
sweep_ordering.py -- does W*_L1 > W*_Box >= W*_L2 hold in ANY regime?

The single-point result (kappa=0.1, gamma=0.667, rho=1, well-conditioned
Gaussian) says no: Box is cheapest and L2 is not. Before rewriting the theorem
we check whether the claim is regime-dependent. The theory makes one sharp,
falsifiable prediction:

    L2 is cheap BECAUSE it is a strict contraction with factor gamma.
    => F*_L2 must FALL as gamma -> 0.

If that holds, a gamma-conditioned theorem survives and the paper keeps its
core. If F*_L2 is flat in gamma, the contraction argument is not what governs
L2 precision (the quantization of gamma itself is), and the ordering claim has
to go.

Also sweeps kappa (Theorem 2 needs samples near the threshold before the
active-set floor can exist at all) and channel conditioning (ADMM is only
interesting when the system is hard; a well-conditioned channel is the easy
case and may be hiding the effect).

Run:  python3 model/sweep_ordering.py           # ~10 min
      python3 model/sweep_ordering.py --quick   # ~2 min, coarser
"""
import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import fxp_admm as FX
from fxp_admm import ProxConfig, admm_fixed, admm_float, vec_fl, to_fx

N, NR, MAX_IT = 8, 32, 64
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)
ALPHA_TARGET = 0.95


def system(seed, rho, cond=None, snr_db=12.0):
    """cond=None -> plain Gaussian. cond=c -> H'H condition number forced to c."""
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((NR, N)) / np.sqrt(NR)
    if cond is not None:
        U, _, Vt = np.linalg.svd(H, full_matrices=False)
        sv = np.logspace(0, -np.log10(cond) / 2, N)
        H = U @ np.diag(sv) @ Vt
        H /= np.linalg.norm(H, 'fro') / np.sqrt(N)
    s = rng.choice([-1.0, 1.0], N)
    p = np.linalg.norm(H @ s) ** 2 / NR
    y = H @ s + rng.standard_normal(NR) * np.sqrt(p / 10 ** (snr_db / 10))
    M = np.linalg.inv(H.T @ H + rho * np.eye(N))
    q = H.T @ y
    # The range bound is ||w||inf <= ||q||inf + rho(||z||inf + ||u||inf), so
    # the safe scale DEPENDS ON RHO. A fixed alpha silently clips at rho != 1
    # -- that is what made the first rho sweep return all-None.
    alpha = min(1.0, ALPHA_TARGET / ((1.0 + rho) * max(np.abs(q).max(), 1e-9)))
    return M, q * alpha, alpha


def fstar(mode, kappa, gamma, rho, cond, trials, target, frange, metric="abs"):
    """Minimum lane fractional width meeting `target` error vs float.

    metric="rel": ||zf-zr||^2 / ||zr||^2. Normalising by a signal whose
        magnitude the operator itself sets is a trap -- the L2 lane shrinks z
        by gamma, so relative error rises as gamma falls and the L2 lane looks
        WORSE the more contractive it is. That is a metric artifact, not
        physics.
    metric="abs" (default): ||zf-zr||^2 / n, compared against target on the
        same fixed scale for all three operators. This is what the theory's
        epsilon-neighbourhood actually means and it is the fair comparison.
    """
    FX.sat_reset()
    for f in frange:
        acc = []
        for t in range(trials):
            M, q, al = system(7000 + t, rho, cond)
            cfg = ProxConfig(f_l1=f, f_box=f, f_l2=f,
                             kappa_q16=to_fx(kappa * al),
                             box_hi_q16=to_fx(1.0 * al),
                             box_lo_q16=to_fx(-1.0 * al),
                             gamma_q16=to_fx(gamma))
            zr, _, _ = admm_float(M, q, mode, N, kappa=cfg.kappa_f,
                                  box=cfg.box_f, gamma=cfg.gamma_f, rho=rho,
                                  max_iter=MAX_IT, eps=1e-9)
            zf = vec_fl(admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT)[0])
            e = np.linalg.norm(zf - zr) ** 2
            if metric == "rel":
                d = np.linalg.norm(zr) ** 2
                acc.append(e / (d if d > 1e-12 else 1.0))
            else:
                acc.append(e / N)
        if np.mean(acc) <= target:
            return f, FX.SAT_COUNT[0]
    return None, FX.SAT_COUNT[0]


def row(label, kappa, gamma, rho, cond, trials, target, frange, metric="abs"):
    res, sat = {}, 0
    for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
        res[nm], s = fstar(mode, kappa, gamma, rho, cond, trials, target,
                           frange, metric)
        sat += s
    a, b, c = res["L1"], res["Box"], res["L2"]
    holds = (a is not None and b is not None and c is not None and a > b >= c)
    flag = "" if sat == 0 else f"  !! {sat} SAT EVENTS - INVALID"
    print(f"  {label:28s} L1={str(a):>4s} Box={str(b):>4s} L2={str(c):>4s}   "
          f"{'HOLDS' if holds else 'fails'}{flag}")
    return {"label": label, **res, "holds": holds, "sat": sat}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--target", type=float, default=1e-4)
    ap.add_argument("--metric", choices=["abs", "rel"], default="abs")
    a = ap.parse_args()
    trials = 20 if a.quick else 60
    frange = range(3, 15)
    out = {"target": a.target, "trials": trials, "rows": []}

    out["metric"] = a.metric
    print(f"metric={a.metric}, target <= {a.target:g}, "
          f"{trials} channels per point\n")

    # A. gamma -- the theory's sharp prediction. F*_L2 must fall as gamma -> 0.
    print("A. contraction factor gamma  (rho=1, kappa=0.1, Gaussian)")
    for g in ([0.9, 0.5, 0.1] if a.quick else [0.95, 0.9, 0.75, 0.5, 0.25, 0.1, 0.05]):
        out["rows"].append(row(f"gamma={g}", 0.1, g, 1.0, None, trials,
                               a.target, frange, a.metric))

    # B. kappa -- Theorem 2 needs mass near the threshold to have any effect.
    print("\nB. L1 threshold kappa  (rho=1, gamma=0.667, Gaussian)")
    for k in ([0.05, 0.3] if a.quick else [0.02, 0.05, 0.1, 0.2, 0.3, 0.5]):
        out["rows"].append(row(f"kappa={k}", k, 0.667, 1.0, None, trials,
                               a.target, frange, a.metric))

    # C. rho -- changes both the conditioning of M and the dual scaling.
    print("\nC. penalty rho  (kappa=0.1, gamma=0.667, Gaussian)")
    for r in ([0.25, 4.0] if a.quick else [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]):
        out["rows"].append(row(f"rho={r}", 0.1, 0.667, r, None, trials,
                               a.target, frange, a.metric))

    # D. conditioning -- ADMM matters when the system is hard. The easy case
    #    may simply be hiding the operator-dependent sensitivity.
    print("\nD. channel condition number  (rho=1, kappa=0.1, gamma=0.667)")
    for c in ([10, 1000] if a.quick else [3, 10, 30, 100, 300, 1000]):
        out["rows"].append(row(f"cond={c}", 0.1, 0.667, 1.0, c, trials,
                               a.target, frange, a.metric))

    n_hold = sum(r["holds"] for r in out["rows"])
    print(f"\n  ordering holds in {n_hold} / {len(out['rows'])} operating points")
    if n_hold == 0:
        print("  -> the theorem as stated is not regime-dependent. It is wrong.")
    elif n_hold < len(out["rows"]) // 3:
        print("  -> holds only in a narrow regime. State that regime explicitly")
        print("     in the theorem, or drop the claim.")
    else:
        print("  -> regime-dependent. Condition the theorem on the sweep")
        print("     variable that separates the two groups.")

    with open(f"{OUT}/ordering_sweep.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\nsaved -> {os.path.relpath(OUT)}/ordering_sweep.json")


if __name__ == "__main__":
    main()
