#!/usr/bin/env python3
"""util_table.py -- resource figures in the metric OTHER PAPERS report.

    python tools/util_table.py

Reads results/syn/<tag>_util_route.rpt (report_utilization -hierarchical,
routed) and prints the top-level row: Total LUTs, FFs, RAMB36/18, DSP.

WHY THIS EXISTS. syn/harvest.tcl counts LUT *cells* (get_cells REF_NAME=~LUT*).
After LUT combining two cells can share one physical LUT6 (LUT6_2), so the
cell count is higher than the "Slice LUTs" every other paper quotes from
report_utilization. For uniform18: 6308 cells vs 4673 LUTs. Cell counts are
fine for within-study ratios of one metric; a comparison table against other
work MUST use this script's numbers.
"""
import os, re, json
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "syn")
TAGS = ["uniform18", "uniform10", "asym_derived", "main10_uniform",
        "main10_lane8", "main9_uniform", "main9_asym"]
rows = {}
for t in TAGS:
    p = os.path.join(HERE, f"{t}_util_route.rpt")
    if not os.path.exists(p):
        continue
    txt = open(p, encoding="utf-8", errors="replace").read()
    assert "Design State : Routed" in txt, f"{p}: not a routed report"
    top = next(l for l in txt.splitlines() if l.startswith("| admm_top"))
    c = [x.strip() for x in top.strip().strip("|").split("|")]
    # Instance | Module | Total LUTs | Logic LUTs | LUTRAMs | SRLs | FFs | RAMB36 | RAMB18 | DSP
    rows[t] = dict(lut=int(c[2]), ff=int(c[6]), ramb36=int(c[7]), ramb18=int(c[8]),
                   dsp=int(c[9]),
                   lut_prox=sum(int(l.strip().strip("|").split("|")[2])
                                for l in txt.splitlines()
                                if re.match(r"\|\s+G_PROX\[\d+\]\.u_prox\s", l)))
print(f"{'tag':15s} {'LUT':>6s} {'LUTprox':>8s} {'FF':>6s} {'BRAM36/18':>10s} {'DSP':>4s}")
for t, r in rows.items():
    print(f"{t:15s} {r['lut']:6d} {r['lut_prox']:8d} {r['ff']:6d} "
          f"{r['ramb36']:>5d}/{r['ramb18']:<4d} {r['dsp']:4d}")
a, b = rows["uniform18"], rows["main9_uniform"]
for k in ("lut", "lut_prox", "ff"):
    print(f"uniform18 -> main9_uniform {k}: {a[k]} -> {b[k]}  {100*(b[k]/a[k]-1):+.1f}%")
json.dump(rows, open(os.path.join(HERE, "..", "util_table.json"), "w"), indent=1)
