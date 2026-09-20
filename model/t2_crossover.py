"""
t2_crossover.py -- falsifier for Theorem 2 (ordering as a function of problem
statistics). Registered BEFORE running.

WHAT IS ALREADY KNOWN. results/ordering_sweep.json shows the lane-width
ordering is NOT fixed: across channel conditioning, Box vs L2 flips (Box
cheaper at cond=3, dearer from cond=30) and L1 vs Box goes from strict to tied.
So T2's HEADLINE -- "no fixed ordering holds" -- is supported. That sweep uses
integer F*, which is too coarse to test a MECHANISM.

WHAT T2 CLAIMS AS MECHANISM. The ordering follows from each operator's
error coefficient at the OPERATOR level (Theorem 1):
    W*_op = W0 + 0.5*log2(A_op)
with A_op from generalize.A_op ((1-d) for L1/Box, gamma^2+E[v^2]+1 for L2).

COMPETING HYPOTHESIS H_loop. The crossover is driven by LOOP GAIN, not by the
operator: L2's contraction pins its loop gain (resolvent saturates at 3.18),
while L1/Box loop gain grows with conditioning. Then
    W*_op = W0 + 0.5*log2(A_op * G_op)
and an operator-only predictor must fail as conditioning grows.

METHOD. Continuous W* instead of integer F*: measure mean absolute error at
lane widths F=4..12, fit log2(err) linear in F on the non-floored region, solve
for err = target. Pairwise gaps dW = W*_a - W*_b are compared against
    pred_op   = 0.5*log2(A_a / A_b)                      (T2 as stated)
    pred_loop = 0.5*log2(A_a*R_a / (A_b*R_b))            (H_loop)
where R_op is the loop resolvent ||(I-T)^-1|| with prox gain g = gamma for L2
and 1 for L1/Box -- an INDEPENDENT quantity computed from M, not fitted.

PREDICTIONS (registered):
  P1  pred_op tracks dW with mean |error| <= 0.5 bit across the sweep.
      FAILS T2's mechanism if not.
  P2  pred_op error GROWS with conditioning (H_loop's signature).
  P3  pred_loop beats pred_op, especially at high conditioning.
  P4  pred_op gets the SIGN of each crossover right. A mechanism that misses
      the direction of a crossover cannot be claimed even if |error| is small.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import fxp_admm as FX
from fxp_admm import ProxConfig, admm_fixed, admm_float, vec_fl, to_fx
from generalize import A_op
from sweep_ordering import system, N, MAX_IT

TARGET = 1e-4
TRIALS = 30
FR = list(range(4, 13))
CONDS = [2, 3, 5, 10, 20, 30, 60, 100, 300, 1000]
KAPPAS = [0.05, 0.1, 0.2, 0.3]
GAMMA, KAPPA, RHO = 0.667, 0.1, 1.0


def resolvent(M, g, rho=RHO):
    I = np.eye(M.shape[0]); A, B = rho * M, I - rho * M
    T = np.block([[g * A, g * B], [(1 - g) * A, (1 - g) * B]])
    return float(np.linalg.norm(np.linalg.inv(np.eye(2 * M.shape[0]) - T), 2))


def cell(mode, kappa, cond):
    """Continuous W*, operator coefficient A, resolvent R, degenerate d."""
    errs = {f: [] for f in FR}
    ds, ev2s, rs = [], [], []
    FX.sat_reset()
    for t in range(TRIALS):
        M, q, al = system(7000 + t, RHO, cond)
        kap, hi = kappa * al, 1.0 * al
        # float trace for d and E[v^2] (same recursion, v recorded)
        z = np.zeros(N); u = np.zeros(N); vs = []
        for _ in range(MAX_IT):
            x = M @ (q + RHO * (z - u)); v = x + u; vs.append(v.copy())
            zn = (np.sign(v) * np.maximum(np.abs(v) - kap, 0) if mode == 0 else
                  np.clip(v, -hi, hi) if mode == 1 else GAMMA * v)
            u = u + x - zn; z = zn
        vs = np.concatenate(vs)
        d = (np.mean(np.abs(vs) <= kap) if mode == 0 else
             np.mean(np.abs(vs) >= hi) if mode == 1 else 0.0)
        ds.append(d); ev2s.append(np.mean(vs ** 2))
        rs.append(resolvent(M, GAMMA if mode == 2 else 1.0))
        for f in FR:
            cfg = ProxConfig(f_l1=f, f_box=f, f_l2=f,
                             kappa_q16=to_fx(kap), box_hi_q16=to_fx(hi),
                             box_lo_q16=to_fx(-hi), gamma_q16=to_fx(GAMMA))
            zr, _, _ = admm_float(M, q, mode, N, kappa=cfg.kappa_f,
                                  box=cfg.box_f, gamma=cfg.gamma_f, rho=RHO,
                                  max_iter=MAX_IT, eps=1e-9)
            zf = vec_fl(admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT)[0])
            errs[f].append(np.linalg.norm(zf - zr) ** 2 / N)
    e = np.array([np.mean(errs[f]) for f in FR])
    # fit on the region where error is well above the F=16 main-path floor
    ok = e > 4 * e.min()
    if ok.sum() < 3:
        ok = np.ones_like(e, bool)
    Fs = np.array(FR)[ok]; le = np.log2(e[ok])
    slope, icpt = np.polyfit(Fs, le, 1)
    wstar = (np.log2(TARGET) - icpt) / slope
    d = float(np.mean(ds))
    return dict(W=float(wstar), slope=float(slope), d=d,
                A=float(A_op(mode, d, np.mean(ev2s))), R=float(np.mean(rs)),
                sat=int(FX.SAT_COUNT[0]))


def main():
    rows = []
    sweep = [("cond", c, KAPPA, c) for c in CONDS] + \
            [("kappa", k, k, 10) for k in KAPPAS]
    print(f"{'axis':6s} {'val':>6s} | {'W*L1':>6s} {'W*Box':>6s} {'W*L2':>6s} | "
          f"{'dL1':>5s} {'dBox':>5s} | {'R_L1':>8s} {'R_L2':>6s} | sat")
    for axis, val, kap, cond in sweep:
        c = {nm: cell(m, kap, cond) for m, nm in ((0, "L1"), (1, "Box"), (2, "L2"))}
        sat = sum(v["sat"] for v in c.values())
        print(f"{axis:6s} {val:6g} | {c['L1']['W']:6.2f} {c['Box']['W']:6.2f} "
              f"{c['L2']['W']:6.2f} | {c['L1']['d']:5.2f} {c['Box']['d']:5.2f} | "
              f"{c['L1']['R']:8.1f} {c['L2']['R']:6.2f} | {sat}"
              + ("  !! SAT -- INVALID" if sat else ""), flush=True)
        rows.append(dict(axis=axis, val=val, cells=c, sat=sat))

    print("\n" + "=" * 74)
    print("pairwise gap dW = W*_a - W*_b : measured vs predicted")
    print("=" * 74)
    out = {"rows": rows, "pairs": {}}
    for a, b in (("L1", "Box"), ("Box", "L2"), ("L1", "L2")):
        eo, el, so, sl, n = [], [], 0, 0, 0
        print(f"\n{a} - {b}")
        print(f"  {'axis':6s} {'val':>6s} {'meas':>7s} {'pred_op':>8s} "
              f"{'pred_loop':>10s}")
        for r in rows:
            if r["sat"]:
                continue
            A, B = r["cells"][a], r["cells"][b]
            meas = A["W"] - B["W"]
            po = 0.5 * np.log2(A["A"] / B["A"])
            pl = 0.5 * np.log2(A["A"] * A["R"] / (B["A"] * B["R"]))
            eo.append(abs(meas - po)); el.append(abs(meas - pl)); n += 1
            if abs(meas) >= 0.25:   # only score sign where the gap is resolvable
                so += np.sign(po) == np.sign(meas)
                sl += np.sign(pl) == np.sign(meas)
            print(f"  {r['axis']:6s} {r['val']:6g} {meas:+7.2f} {po:+8.2f} {pl:+10.2f}")
        ns = sum(1 for r in rows if not r["sat"] and
                 abs(r["cells"][a]["W"] - r["cells"][b]["W"]) >= 0.25)
        print(f"  mean |err|  op {np.mean(eo):.3f} bits   loop {np.mean(el):.3f} bits"
              f"   sign right (|gap|>=0.25): op {so}/{ns}  loop {sl}/{ns}")
        out["pairs"][f"{a}-{b}"] = dict(err_op=float(np.mean(eo)),
                                        err_loop=float(np.mean(el)),
                                        sign_op=int(so), sign_loop=int(sl),
                                        n_sign=int(ns))
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "results"), exist_ok=True)
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "..",
                                     "results", "t2_crossover.json"), "w"),
              indent=1, default=float)
    print("\n  saved -> results/t2_crossover.json")


if __name__ == "__main__":
    main()
