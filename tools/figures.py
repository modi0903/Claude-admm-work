#!/usr/bin/env python3
"""figures.py -- every figure in the FCCM draft, from committed code and data.

    python tools/figures.py        # writes paper/fccm/fig_*.pdf

fig_builds.pdf  F_max vs Slice LUTs for the seven builds, by critical-path
      family, with the board's in-context points for the two headline builds.
      Data: results/util_table.json (LUT), results/syn/fmax_all2.log (F_max),
      BOARD.md session 2 (in-context met frequencies).

fig_t1.pdf  Theorem 1 against bit-exact measurement.
  (a) operator error vs degenerate fraction d: L1 and Box swept by their
      parameter (model/annihilation.py, on-lattice, F=8); the (1-d) q^2/12
      prediction; the classical flat q^2/12.
  (b) the same as ratios, adding the five LASSO points measured on that
      problem's native distribution (results/lasso.json, off-lattice kappa).
Recomputed, not read from a cache: annihilation.py is deterministic (seeded)
and takes about a second.
"""
import contextlib, io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "model"))
OUT = os.path.join(ROOT, "paper", "fccm")

# reference palette, first three categorical slots (validated all-pairs);
# marker shape is a second encoding so the figure survives greyscale print
C_L1, C_BOX, C_LASSO = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 7.5, "font.family": "serif", "axes.linewidth": 0.6,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "legend.frameon": False, "pdf.fonttype": 42,
})


def t1_figure():
    import annihilation as A
    with contextlib.redirect_stdout(io.StringIO()):
        v_raw = A.harvest_v()
        v_fx = np.array([A.to_fx(x) for x in v_raw])
        v_ref = np.array([A.to_fl(x) for x in v_fx])
        r1 = A.sweep(0, [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.4], v_ref, v_fx)
        r2 = A.sweep(1, [1.4, 1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.05, 0.02], v_ref, v_fx)
    q2 = (2.0 ** -A.F_TEST) ** 2 / 12.0
    lasso = json.load(open(os.path.join(ROOT, "results", "lasso.json")))["e1"]

    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 3.3), sharex=True,
                                 gridspec_kw=dict(height_ratios=[1.15, 1], hspace=0.12))
    d = np.linspace(0, 0.9995, 400)
    for a in (ax, bx):
        a.grid(True, which="major", color=GRID, linewidth=0.5)
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)

    # (a) absolute error
    ax.axhline(q2, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2, label=r"classical $q^2/12$")
    ax.plot(d, (1 - d) * q2, color=INK, linewidth=1.2, label=r"Theorem 1: $(1-d)\,q^2/12$")
    for rows, c, m, lab in ((r1, C_L1, "o", "L1, measured"), (r2, C_BOX, "s", "Box, measured")):
        pts = [(x[1], x[2]) for x in rows if x[2] > 0]
        ax.plot(*zip(*pts), linestyle="none", marker=m, markersize=4.2, color=c,
                markeredgecolor="white", markeredgewidth=0.6, label=lab)
    ax.set_yscale("log")
    ax.set_ylabel("operator MSE")
    ax.legend(loc="lower left", fontsize=6.6, handlelength=2.2, borderaxespad=0.2)
    ax.set_title("(a)", loc="left", fontsize=7.5, color=INK, pad=2)

    # (b) ratios
    bx.axhline(1.0, color=INK, linewidth=1.0)
    bx.plot(d[d < 0.995], 1 / (1 - d[d < 0.995]), color=INK2, linestyle=(0, (4, 3)),
            linewidth=1.2, label=r"classical/measured if T1 holds: $1/(1-d)$")
    for rows, c, m in ((r1, C_L1, "o"), (r2, C_BOX, "s")):
        pts = [(x[1], x[3] / x[2]) for x in rows if x[2] > 0]
        bx.plot(*zip(*pts), linestyle="none", marker=m, markersize=4.2, color=c,
                markeredgecolor="white", markeredgewidth=0.6)
        pts = [(x[1], q2 / x[2]) for x in rows if x[2] > 0]
        bx.plot(*zip(*pts), linestyle="none", marker=m, markersize=4.2,
                markerfacecolor="none", markeredgecolor=c, markeredgewidth=0.8)
    bx.plot([r["d"] for r in lasso], [r["t1_ratio"] for r in lasso], linestyle="none",
            marker="^", markersize=4.6, color=C_LASSO, markeredgecolor="white",
            markeredgewidth=0.6, label="LASSO, native distribution")
    bx.plot([r["d"] for r in lasso], [r["classical_ratio"] for r in lasso], linestyle="none",
            marker="^", markersize=4.6, markerfacecolor="none", markeredgecolor=C_LASSO,
            markeredgewidth=0.8)
    bx.set_yscale("log")
    bx.set_ylim(0.5, 1500)
    bx.set_ylabel("prediction / measured")
    bx.set_xlabel(r"degenerate fraction $d$")
    bx.set_xlim(-0.02, 1.02)
    bx.text(0.02, 0.62, "filled: Theorem 1\nhollow: classical", transform=bx.transAxes,
            ha="left", va="center", color=INK2, fontsize=6.6)
    bx.legend(loc="upper left", fontsize=6.6, handlelength=2.2, borderaxespad=0.2)
    bx.set_title("(b)", loc="left", fontsize=7.5, color=INK, pad=2)

    fig.savefig(os.path.join(OUT, "fig_t1.pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(os.path.join(OUT, "fig_t1.png"), dpi=220, bbox_inches="tight", pad_inches=0.02)
    print("wrote paper/fccm/fig_t1.pdf")


def fmax_log():
    """FMAX SUMMARY rows from the committed sweep log."""
    txt = open(os.path.join(ROOT, "results", "syn", "fmax_all2.log"),
               encoding="utf-8", errors="replace").read()
    block = txt.split("======================== FMAX SUMMARY ========================")[-1]
    out = {}
    for line in block.splitlines():
        f = line.split()
        if len(f) == 4 and f[0] != "tag":
            try:
                out[f[0]] = float(f[2])
            except ValueError:
                pass
    return out


def builds_figure():
    u = json.load(open(os.path.join(ROOT, "results", "util_table.json")))
    fm = fmax_log()
    # tag: (label, critical-path family) -- family from results/syn/critpath.log
    B = {"uniform18": ("Q2.16", "A"), "uniform10": ("16 / lanes 8", "A"),
         "asym_derived": ("16 / 8-7-8", "A"), "main10_lane8": ("10 / lanes 8", "A"),
         "main10_uniform": ("Q2.10", "B"), "main9_uniform": ("Q2.9", "B"),
         "main9_asym": ("9 / 9-8-9", "B")}
    board = {"uniform18": 65.0, "main9_uniform": 82.5}   # BOARD.md session 2
    fig, ax = plt.subplots(figsize=(3.45, 2.15))
    ax.grid(True, color=GRID, linewidth=0.5); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.axhspan(63, 70, color=C_BOX, alpha=0.07, linewidth=0)
    ax.axhspan(78.5, 88, color=C_L1, alpha=0.07, linewidth=0)
    ax.text(5000, 63.4, "lane path binds (A)", ha="right", va="bottom", color=INK2, fontsize=6.6)
    ax.text(5000, 87.6, "convergence test binds (B)", ha="right", va="top", color=INK2, fontsize=6.6)
    off = {"uniform18": (6, 3, "left"), "uniform10": (5, 4, "left"),
           "asym_derived": (6, -1, "left"), "main10_lane8": (4, 8, "left"),
           "main10_uniform": (5, -3, "left"), "main9_uniform": (-6, 3, "right"),
           "main9_asym": (6, 1, "left")}
    for t, (lab, fam) in B.items():
        c, m = (C_BOX, "o") if fam == "A" else (C_L1, "s")
        ax.plot(u[t]["lut"], fm[t], marker=m, markersize=5, color=c,
                markeredgecolor="white", markeredgewidth=0.6, linestyle="none")
        dx, dy, ha = off[t]
        ax.annotate(lab, (u[t]["lut"], fm[t]), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va="center", fontsize=6.4, color=INK)
    for t, f in board.items():
        ax.plot(u[t]["lut"], f, marker="D", markersize=4, markerfacecolor="none",
                markeredgecolor=INK, markeredgewidth=0.8, linestyle="none")
    ax.annotate("", xy=(u["main9_uniform"]["lut"] + 60, fm["main9_uniform"] - 0.6),
                xytext=(u["uniform18"]["lut"] - 60, fm["uniform18"] + 0.6),
                arrowprops=dict(arrowstyle="-|>", color=INK2, linewidth=0.8,
                                connectionstyle="arc3,rad=-0.15", shrinkA=4, shrinkB=4))
    ax.plot([], [], marker="D", markerfacecolor="none", markeredgecolor=INK,
            linestyle="none", markersize=4, label="on board, in context")
    ax.legend(loc="lower left", fontsize=6.4, borderaxespad=0.2)
    ax.set_xlabel("Slice LUTs")
    ax.set_ylabel(r"$F_{\max}$ (MHz)")
    ax.set_xlim(2300, 5050); ax.set_ylim(60, 89)
    fig.savefig(os.path.join(OUT, "fig_builds.pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(os.path.join(OUT, "fig_builds.png"), dpi=220, bbox_inches="tight", pad_inches=0.02)
    print("wrote paper/fccm/fig_builds.pdf")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    t1_figure()
    builds_figure()
