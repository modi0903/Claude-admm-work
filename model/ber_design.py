"""
ber_design.py -- does the Q2.9 design point cost detection accuracy?

Uncoded BER of Box-constrained ADMM detection (BPSK, 32x8 real, rho=1,
32 iterations) for: linear MMSE, double-precision ADMM, Q2.16 (the
baseline build) and Q2.9 (the design point), using the same bit-exact
fixed-point runner and the same constant snapping as main_sweep.py, i.e. the
datapath that was measured on silicon.

experiments.py E3 compared float / Q2.16 / an old asymmetric preset and never
the design point, with 400 trials -- too few to resolve BER below ~3e-4. This
run uses 3000 trials (24000 bits) per SNR and also reports how often Q2.9
makes exactly the same 8 decisions as double precision.

PREDICTION, registered before running: Q2.9 BER equals double-precision BER
to within the 95% binomial interval at every SNR, and its decisions agree
with double precision on >= 99.9% of bits.

RESULT (2026-10-04): the BER prediction HOLDS at every SNR. The agreement
prediction FAILS AS REGISTERED at 0 dB: 99.896% (25 of 24000 bits), passing
at every other SNR. Reported as a miss, not re-thresholded.
"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from experiments import system, N, RHO
from fxp_admm import admm_float
from main_sweep import run_fixed, snap, KAPPA, BOXHI, GAMMA

TRIALS, ITERS = 3000, 32
SNRS = (0, 2, 4, 6, 8, 10, 12, 14)
HERE = os.path.dirname(__file__)


def wilson(k, n, z=1.96):
    # k = 0 has an exact lower bound of 0. Computing it through the general
    # formula leaves ~1e-20 of rounding, which made "0 inside the interval"
    # test false on the first run -- an arithmetic bug, not a result.
    if k == 0:
        return 0.0, z * z / (n + z * z)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), c + h


def main():
    rows = []
    print(f"BER, Box-constrained ADMM detection, BPSK 32x8, {TRIALS} trials x {N} bits per SNR\n")
    print(f"{'SNR':>4s} {'MMSE':>9s} {'float':>9s} {'Q2.16':>9s} {'Q2.9':>9s}   "
          f"{'Q2.9 95% CI':>21s}   agree w/ float")
    for snr in SNRS:
        e = dict(mmse=0, float=0, q16=0, q9=0)
        agree9 = 0
        for t in range(TRIALS):
            M, q, s, al = system(seed=61000 + t + 977 * snr, snr_db=snr)
            e["mmse"] += int(np.sum(np.sign(M @ q) != s))
            zf, _, _ = admm_float(M, q, 1, N, box=(-al, al), rho=RHO,
                                  max_iter=ITERS, eps=0.0)
            df = np.sign(zf)
            e["float"] += int(np.sum(df != s))
            for key, f in (("q16", 16), ("q9", 9)):
                zq = run_fixed(M, q, 1, f, f, f, f, snap(KAPPA * al, f),
                               snap(BOXHI * al, f), snap(GAMMA, f), iters=ITERS)
                dq = np.sign(zq)
                e[key] += int(np.sum(dq != s))
                if key == "q9":
                    agree9 += int(np.sum(dq == df))
        n = TRIALS * N
        lo, hi = wilson(e["q9"], n)
        r = dict(snr=snr, bits=n, **{k: v / n for k, v in e.items()},
                 q9_ci=[lo, hi], q9_agree_float=agree9 / n,
                 errors={k: v for k, v in e.items()})
        rows.append(r)
        print(f"{snr:4d} {r['mmse']:9.2e} {r['float']:9.2e} {r['q16']:9.2e} {r['q9']:9.2e}   "
              f"[{lo:8.2e}, {hi:8.2e}]   {100*r['q9_agree_float']:.3f}%", flush=True)
    worst = min(r["q9_agree_float"] for r in rows)
    inci = all(r["q9_ci"][0] <= r["float"] <= r["q9_ci"][1] for r in rows)
    print(f"\nprediction: float BER inside Q2.9's 95% CI at every SNR -> {'HOLDS' if inci else 'FAILS'}")
    print(f"prediction: Q2.9 agrees with float on >= 99.9% of bits -> worst {100*worst:.3f}% "
          f"-> {'HOLDS' if worst >= 0.999 else 'FAILS'}")
    json.dump(rows, open(os.path.join(HERE, "..", "results", "ber_design.json"), "w"), indent=1)
    print("saved -> results/ber_design.json")


if __name__ == "__main__":
    main()
