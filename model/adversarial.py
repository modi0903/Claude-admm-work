"""
adversarial.py -- can the fitted loop-gain model be BROKEN on purpose?

THE THREAT. Kinsman & Nicolici (TCAD 2011, Sect. V-D-4) break a conjugate-
gradient design whose wordlengths were validated by 50-point Monte Carlo. They
do it by choosing a right-hand side equally weighted across the eigenvectors of
the system matrix. The resulting error sits ~35 standard deviations beyond the
simulated worst case. They further show double precision is not immune. Their
point: empirical validation over random instances says nothing about the corner.

Our loop-gain model is fitted and cross-validated over RANDOM conditioning
sweeps with random right-hand sides. The same attack applies to us, and a
reviewer holding that paper will make it. This script makes it first.

WHY NOT A WORST-CASE BOUND INSTEAD. Turning T1 into a guaranteed bound needs
Lyapunov or interval machinery -- exactly what Jerez et al. and Kinsman &
Nicolici already have. Their bounds are conservative by construction (hundreds
of bits for CG; near single-to-double precision after heavy restriction), which
is the deficiency our predictive model exists to address. Competing there means
losing on their ground with their tools. The defensible move is to attack our
own model empirically and then SCOPE the claim to whatever survives.

THE ATTACK. For each operator and conditioning level, hold the system matrix
fixed and search over right-hand sides:
    random      -- the distribution the model was fitted on (baseline)
    eig-equal   -- Kinsman's attack: equal weight across all eigenvectors
    eig-min     -- aligned to the smallest singular direction
    eig-max     -- aligned to the largest singular direction
    hill-climb  -- greedy search maximising |model - measured| in bits

PREDICTIONS, each of which can fail:
    P1  eig-equal produces model error worse than random.
    P2  hill-climb finds instances outside the 0.5-bit criterion.
    P3  the worst case found is BOUNDED, i.e. the search plateaus rather than
        diverging.

If P3 fails -- if the error grows without limit as the search runs -- the model
cannot be scoped by an empirical worst case and the paper must say so plainly.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from generalize import (admm_float, admm_fixed, snap_lat, A_op, RHO,
                        KAPPA, BOXHI, GAMMA, ALPHA_TARGET)
from loop_gain import resolvent, N, F, q2_12

CRIT = 0.5          # bits, the criterion the model is claimed against
CONDS = [1.0, 10.0, 60.0, 300.0]
TRIALS = 12         # systems per conditioning
HILL_STEPS = 60     # greedy iterations
HILL_RESTARTS = 3


def build_H(c, seed):
    """System matrix at controlled conditioning. Mirrors loop_gain.system_cond,
    but returns H so the right-hand side can be chosen adversarially."""
    rng = np.random.default_rng(seed)
    nr = 4 * N
    H = rng.standard_normal((nr, N)) / np.sqrt(nr)
    if c > 1.0:
        U, s, Vt = np.linalg.svd(H, full_matrices=False)
        s = np.geomspace(s[0], s[0] / c, len(s))
        H = U @ np.diag(s) @ Vt
    return H, rng


def q_from_dir(H, w, rng):
    """Right-hand side from a coefficient direction w.

    Mirrors loop_gain.system_cond EXACTLY except that the coefficient vector x
    is chosen (adversarially) instead of drawn as random +-1. Two details are
    load-bearing and were wrong in the first version of this script:
      * `a` is a SCALE FACTOR (min(1, ALPHA_TARGET/max|q|), always <= 1) applied
        to BOTH q and the lane thresholds -- not an amplitude. Getting this
        wrong rescales kappa and makes d meaningless.
      * the observation noise must be kept, or the instance is not drawn from
        the family the model was fitted on and the comparison is void.
    x is normalised to ||x|| = sqrt(N) to match the +-1 vector it replaces.
    """
    nr = H.shape[0]
    x = w / (np.linalg.norm(w) + 1e-300) * np.sqrt(N)
    p = np.linalg.norm(H @ x) ** 2 / nr
    y = H @ x + rng.standard_normal(nr) * np.sqrt(p / 10 ** 1.2)
    q = H.T @ y
    a = min(1.0, ALPHA_TARGET / max(np.abs(q).max(), 1e-9))
    return q * a, a


def measure(M, q, a, mode):
    """Measured loop gain G and degenerate fraction d for one instance."""
    kap = snap_lat(KAPPA * a, F)
    hi = snap_lat(BOXHI * a, F)
    gam = snap_lat(GAMMA, F)
    zr, vs = admm_float(M, q, mode, N, kap, hi, gam)
    zf = admm_fixed(M, q, mode, N, F, kap, hi, gam)
    d = (np.mean(np.abs(vs) <= kap) if mode == 0 else
         np.mean(np.abs(vs) >= hi) if mode == 1 else 0.0)
    A = A_op(mode, d, np.mean(vs ** 2))
    mse = np.mean((zf - zr) ** 2)
    if A <= 0 or mse <= 0:
        return None
    return dict(G=float(mse / q2_12 / A), d=float(d),
                nm=float(np.linalg.norm(M, 2)),
                res=float(resolvent(M, GAMMA if mode == 2 else 1.0)))


def predict(coef, r, mode):
    """Fitted model: log G = a*log(1/(1-||M||2)) + b*R_op + c."""
    base = np.log(1.0 / (1.0 - r["nm"] + 1e-6))
    R = r["d"] if mode == 0 else (r["d"] ** 2 if mode == 1 else 0.0)
    if mode == 2:
        return coef[0] * np.log(r["res"]) + coef[-1]
    return coef[0] * base + coef[1] * R + coef[-1]


def bits_signed(coef, r, mode):
    """SIGNED model error in bits. Sign is the whole story:
      positive -> measured G exceeds prediction: the model UNDER-predicts error,
                  so wordlengths chosen from it would be TOO FEW. Dangerous.
      negative -> the model OVER-predicts: conservative, wastes bits, safe.
    Reporting only |error| conflates a safety failure with a safety margin."""
    return (np.log(r["G"]) - predict(coef, r, mode)) / (2 * np.log(2))


def bits_err(coef, r, mode):
    return abs(bits_signed(coef, r, mode))


def fit_baseline(mode, coefspec):
    """Refit on random instances so the attack targets an honestly fitted
    model rather than coefficients tuned on the attack itself."""
    rows = []
    for c in np.geomspace(1.0, 300.0, 12):
        for t in range(8):
            H, rng = build_H(c, 5000 + t)
            w = rng.choice([-1.0, 1.0], N)
            q, a = q_from_dir(H, w, rng)
            M = np.linalg.inv(H.T @ H + RHO * np.eye(N))
            r = measure(M, q, a, mode)
            if r:
                rows.append(r)
    y = np.log([r["G"] for r in rows])
    base = np.log([1.0 / (1.0 - r["nm"] + 1e-6) for r in rows])
    one = np.ones_like(base)
    if mode == 2:
        X = np.vstack([np.log([r["res"] for r in rows]), one]).T
    else:
        R = np.array([r["d"] if mode == 0 else r["d"] ** 2 for r in rows])
        X = np.vstack([base, R, one]).T
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = [abs(v) for v in (y - X @ coef)]
    return coef, float(np.mean(resid) / (2 * np.log(2)))


def main():
    out = {}
    print("SIGNED bits: + = model UNDER-predicts error (UNSAFE, too few bits)")
    print("             - = model OVER-predicts (conservative, safe)")
    print(f"{'op':4s} {'attack':>17s} {'cond':>7s} {'worst+':>9s} {'worst-':>9s} "
          f"{'d':>6s} {'verdict':>7s}")
    for mode, nm in ((0, "L1"), (1, "Box"), (2, "L2")):
        coef, insample = fit_baseline(mode, None)
        print(f"# {nm}: baseline in-sample error {insample:.3f} bits "
              f"(random right-hand sides)")
        worst = {}
        for c in CONDS:
            for t in range(TRIALS):
                H, rng = build_H(c, 9000 + t)
                M = np.linalg.inv(H.T @ H + RHO * np.eye(N))
                U, s, Vt = np.linalg.svd(H, full_matrices=False)

                cands = {
                    "random":    rng.choice([-1.0, 1.0], N),
                    "eig-equal": Vt.sum(axis=0),          # Kinsman's attack
                    "eig-min":   Vt[-1],
                    "eig-max":   Vt[0],
                }
                for label, w in cands.items():
                    q, a = q_from_dir(H, w, rng)
                    r = measure(M, q, a, mode)
                    if r:
                        e = bits_signed(coef, r, mode)
                        k = (label, c)
                        cur = worst.get(k, (-1e9, 1e9, 0))
                        worst[k] = (max(e, cur[0]), min(e, cur[1]), r["d"])

                # greedy search: perturb the direction to maximise model error
                for _ in range(HILL_RESTARTS):
                    w = rng.standard_normal(N)
                    q, a = q_from_dir(H, w, rng)
                    r = measure(M, q, a, mode)
                    best = bits_signed(coef, r, mode) if r else -1e9
                    bd = r["d"] if r else 0.0
                    step = 0.6
                    for _ in range(HILL_STEPS):
                        w2 = w + step * rng.standard_normal(N)
                        q2, a2 = q_from_dir(H, w2, rng)
                        r2 = measure(M, q2, a2, mode)
                        if not r2:
                            continue
                        e2 = bits_signed(coef, r2, mode)
                        if e2 > best:
                            best, w, bd = e2, w2, r2["d"]
                        else:
                            step *= 0.93
                    k = ("hill-climb-under", c)
                    cur = worst.get(k, (-1e9, 1e9, 0))
                    worst[k] = (max(best, cur[0]), min(best, cur[1]), bd)

        for (label, c), (hi, lo, d) in sorted(worst.items()):
            print(f"{nm:4s} {label:>17s} {c:7.1f} {hi:+9.2f} {lo:+9.2f} "
                  f"{d:6.3f} {'UNSAFE' if hi > CRIT else 'ok':>7s}")
        out[nm] = dict(coef=[float(v) for v in coef], in_sample=insample,
                       worst={f"{k[0]}@{k[1]}": [float(v[0]), float(v[1]),
                                                 float(v[2])]
                              for k, v in worst.items()})

    os.makedirs("results", exist_ok=True)
    json.dump(out, open("results/adversarial.json", "w"), indent=1)
    print("\n  saved -> results/adversarial.json")


if __name__ == "__main__":
    main()
