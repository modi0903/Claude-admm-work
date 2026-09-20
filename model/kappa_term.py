"""
kappa_term.py -- does the parameter-quantisation term close the T2 L1-Box gap?
(TODO item 4)

t2_crossover.py predicts dW(L1-Box) 0.4-0.6 bits too LOW and is flat in kappa
while the measured gap falls with kappa. The candidate is Corollary 1a's
theta term, which generalize.A_op omits for L1 and Box:

  L1 : on D^c the output is v - sign(v)*kappa, so kappa's quantisation error
       e_k adds directly:        A_L1  = (1-d_L1) * (1 + e_k^2 / (q^2/12))
  Box: on D the output IS the bound, so its quantisation error e_h adds:
       A_Box = (1-d_Box) + d_Box * e_h^2 / (q^2/12)
       (the bound is NOT a power of two after alpha-normalisation, so
        Corollary 1a's "Box has no theta term" does not hold here)

e_k, e_h are the ACTUAL deterministic lattice errors of the constants as the
hardware holds them (Q2.16 spec, rounded to lane width f), averaged over the
trials and over the lane widths that set W*. Nothing is fitted.

Registered predictions:
  K1  the corrected predictor reduces the L1-Box mean error below 0.355 bits.
  K2  it reproduces the measured DOWNWARD trend of dW(L1-Box) with kappa.
      If K1 holds but K2 fails, the fix is a constant offset, not a mechanism.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from fxp_admm import ProxConfig, to_fx
from sweep_ordering import system

RHO, TRIALS, GAMMA = 1.0, 30, 0.667
HERE = os.path.dirname(__file__)


def lattice_err2(kap, hi, fs):
    """Mean over lane widths of (e/q)^2*12 for kappa and the box bound."""
    ek, eh = [], []
    for f in fs:
        cfg = ProxConfig(f_l1=f, f_box=f, f_l2=f, kappa_q16=to_fx(kap),
                         box_hi_q16=to_fx(hi), box_lo_q16=to_fx(-hi),
                         gamma_q16=to_fx(GAMMA))
        q = 2.0 ** -f
        ek.append(12 * ((cfg.kappa / 2.0 ** f - kap) / q) ** 2)
        eh.append(12 * ((cfg.box_hi / 2.0 ** f - hi) / q) ** 2)
    return np.mean(ek), np.mean(eh)


def wstar_geo(mode, kappa, cond, T=TRIALS, fr=range(4, 13), target=1e-4):
    """Continuous W* from the GEOMETRIC mean of per-instance error."""
    from fxp_admm import admm_fixed, admm_float, vec_fl
    from sweep_ordering import N, MAX_IT
    E = {f: [] for f in fr}
    for t in range(T):
        M, q, al = system(7000 + t, RHO, cond)
        kap, hi = kappa * al, al
        for f in fr:
            cfg = ProxConfig(f_l1=f, f_box=f, f_l2=f, kappa_q16=to_fx(kap),
                             box_hi_q16=to_fx(hi), box_lo_q16=to_fx(-hi),
                             gamma_q16=to_fx(GAMMA))
            zr, _, _ = admm_float(M, q, mode, N, kappa=cfg.kappa_f, box=cfg.box_f,
                                  gamma=cfg.gamma_f, rho=RHO, max_iter=MAX_IT, eps=1e-9)
            zf = vec_fl(admm_fixed(M, q, mode, N, cfg, max_iter=MAX_IT)[0])
            E[f].append(max(np.linalg.norm(zf - zr) ** 2 / N, 1e-30))
    fr = list(fr)
    e = np.array([np.exp(np.mean(np.log(E[f]))) for f in fr])
    ok = e > 4 * e.min()
    if ok.sum() < 3:
        ok[:] = True
    s, c = np.polyfit(np.array(fr)[ok], np.log2(e[ok]), 1)
    top = float(np.mean([max(E[f]) / sum(E[f]) for f in fr]))
    return (np.log2(target) - c) / s, top


def main():
    t2 = json.load(open(os.path.join(HERE, "..", "results", "t2_crossover.json")))
    print(f"{'axis':6s} {'val':>6s} | {'meas':>6s} {'pred0':>6s} {'predK':>6s} | "
          f"{'k_L1':>5s} {'h_Box':>5s}")
    e0, eK, rows = [], [], []
    for r in t2["rows"]:
        kappa = r["val"] if r["axis"] == "kappa" else 0.1
        cond = 10 if r["axis"] == "kappa" else r["val"]
        L, B = r["cells"]["L1"], r["cells"]["Box"]
        # lane widths that actually set W*: the integers bracketing it
        fs = sorted({int(np.floor(w)) + k for w in (L["W"], B["W"]) for k in (0, 1)})
        ks, hs = [], []
        for t in range(TRIALS):
            M, q, al = system(7000 + t, RHO, cond)
            a, b = lattice_err2(kappa * al, 1.0 * al, fs)
            ks.append(a); hs.append(b)
        k, h = float(np.mean(ks)), float(np.mean(hs))
        A_L1 = (1 - L["d"]) * (1 + k)
        A_B = (1 - B["d"]) + B["d"] * h
        meas = L["W"] - B["W"]
        p0 = 0.5 * np.log2(L["A"] / B["A"])
        pK = 0.5 * np.log2(A_L1 / A_B)
        e0.append(abs(meas - p0)); eK.append(abs(meas - pK))
        rows.append(dict(axis=r["axis"], val=r["val"], meas=meas, pred0=p0,
                         predK=pK, k=k, h=h))
        print(f"{r['axis']:6s} {r['val']:6g} | {meas:+6.2f} {p0:+6.2f} {pK:+6.2f} | "
              f"{k:5.2f} {h:5.2f}")
    kap = [x for x in rows if x["axis"] == "kappa"]
    tm = np.polyfit([x["val"] for x in kap], [x["meas"] for x in kap], 1)[0]
    tp = np.polyfit([x["val"] for x in kap], [x["predK"] for x in kap], 1)[0]
    print(f"\nL1-Box mean |err|: operator-only {np.mean(e0):.3f} bits -> with theta "
          f"terms {np.mean(eK):.3f} bits")
    print(f"kappa trend (bits per unit kappa): measured {tm:+.2f}, predicted {tp:+.2f}")
    # ---- K3: is the residual an OUTLIER artefact of mean-based W*? -------
    # Recompute W* from the GEOMETRIC mean of per-instance error. If the L1-Box
    # residual and the kappa trend vanish, they were driven by rare bad
    # instances rather than by the operator.
    print("\nK3: W* from geometric-mean error (outlier test)")
    eg, kg = [], []
    for x, r in zip(rows, t2["rows"]):
        kappa = r["val"] if r["axis"] == "kappa" else 0.1
        cond = 10 if r["axis"] == "kappa" else r["val"]
        Lg, sl = wstar_geo(0, kappa, cond)
        Bg, sb = wstar_geo(1, kappa, cond)
        x["meas_geo"] = Lg - Bg; x["top_L1"] = sl; x["top_Box"] = sb
        eg.append(abs(Lg - Bg - x["pred0"]))
        if r["axis"] == "kappa":
            kg.append((kappa, Lg - Bg))
        print(f"  {r['axis']:6s} {r['val']:6g}  gap(geo) {Lg-Bg:+.2f}  "
              f"top-instance share L1 {sl:.0%} Box {sb:.0%}", flush=True)
    tg = np.polyfit([a for a, _ in kg], [v for _, v in kg], 1)[0]
    print(f"L1-Box mean |err| vs geometric W*: {np.mean(eg):.3f} bits; "
          f"kappa trend {tg:+.2f} bits/unit")
    json.dump(dict(rows=rows, err0=float(np.mean(e0)), errK=float(np.mean(eK)),
                   trend_meas=float(tm), trend_pred=float(tp),
                   err_geo=float(np.mean(eg)), trend_geo=float(tg)),
              open(os.path.join(HERE, "..", "results", "kappa_term.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
