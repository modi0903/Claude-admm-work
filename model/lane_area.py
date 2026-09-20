"""lane_area.py -- FALSIFIER for the linear lane-area law, on BOTH LUT metrics.

T3 claims A_lane(W) = b*W + c at whole-lane granularity, fitted on LUT CELL
counts (harvest.tcl) and validated out-of-sample at -6.3%. The comparison
table (COMPARISON.md) quotes Slice LUTs instead, because that is what other
papers report. If the law is a property of the design it must survive the
change of metric; if it does not, the claim is a property of LUT combining and
must be scoped.

Fit on the three builds whose lanes equal F_MAIN (no cast in the lane path):
W = 16, 10, 9. Predict W = 8 and compare against the two measured lane-8
builds, which differ only in cast depth (F_MAIN 16 vs 10).

    python model/lane_area.py
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
U = json.load(open(os.path.join(HERE, "..", "results", "util_table.json")))
NPROX = 8                      # G_PROX[0..7]

# LUT cells per build, from syn/harvest.tcl (STATUS.md six-build table)
# main10_lane8 was never harvested with harvest.tcl, so it has no cell count.
# Do not estimate one: a scaled cell count is a fabricated measurement.
CELLS = {"uniform18": 2720, "uniform10": 1232, "main10_uniform": 1544,
         "main9_uniform": 1184}
# lane width W and F_MAIN per build
CFG = {"uniform18": (16, 16), "uniform10": (8, 16), "main10_uniform": (10, 10),
       "main10_lane8": (8, 10), "main9_uniform": (9, 9)}
FIT = ["uniform18", "main10_uniform", "main9_uniform"]     # lanes == F_MAIN
HELD = ["uniform10", "main10_lane8"]                        # lane 8, cast present


def series(metric):
    if metric == "slice":
        return {t: U[t]["lut_prox"] / NPROX for t in CFG}
    return {t: CELLS[t] / NPROX for t in CFG if t in CELLS}


def run(metric):
    a = series(metric)
    W = np.array([CFG[t][0] for t in FIT], float)
    A = np.array([a[t] for t in FIT], float)
    b, c = np.polyfit(W, A, 1)
    r = A - (b * W + c)
    print(f"\n=== {metric} LUTs per lane ===")
    for t in FIT:
        w = CFG[t][0]
        print(f"  fit   {t:15s} W={w:2d}  measured {a[t]:7.1f}  "
              f"model {b*w+c:7.1f}  {100*(b*w+c)/a[t]-100:+6.1f}%")
    print(f"  b = {b:.2f} LUT/bit   c = {c:.1f} LUT   max fit residual "
          f"{np.abs(r).max():.1f} LUT")
    for t in [h for h in HELD if h in a]:
        w, fm = CFG[t]
        p = b * w + c
        print(f"  HELD  {t:15s} W={w:2d} (F_MAIN={fm})  measured {a[t]:7.1f}  "
              f"predicted {p:7.1f}  {100*p/a[t]-100:+6.1f}%")
    return b, c, a


if __name__ == "__main__":
    print("LINEAR LANE-AREA LAW -- does it survive the change of LUT metric?")
    out = {m: run(m) for m in ("cells", "slice")}
    bc, _, ac = out["cells"]; bs, _, as_ = out["slice"]
    print(f"\n  slope: {bc:.2f} LUT/bit (cells) vs {bs:.2f} (Slice LUTs), "
          f"ratio {bs/bc:.2f}")
    d = as_["uniform10"] - as_["main10_lane8"]
    print("  cast cost (Slice LUTs, the two lane-8 builds: same W, cast depth 8 vs 2):")
    print(f"    {as_['uniform10']:.1f} - {as_['main10_lane8']:.1f} = {d:.1f} "
          f"LUT/lane over 6 bits of cast -> {d/6:.2f} LUT/bit/lane")
    print("    (no cell-count equivalent: main10_lane8 was never harvested.)")
