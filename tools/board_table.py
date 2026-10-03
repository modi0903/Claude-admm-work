#!/usr/bin/env python3
"""board_table.py -- in-context Fmax brackets from the board builds.

    python tools/board_table.py

Reads results/syn/board_<tag>_<rom>_mmcm<MHz>_timing.rpt (written by
syn/board_build.tcl), takes WNS/WHS from the Design Timing Summary, and for
each build reports the highest frequency that MET (setup AND hold) and the
lowest that MISSED above it. The in-context Fmax is quoted as that bracket.
It is never 1000/(period - slack): slack at one constraint does not predict
the router's result at another, which is why this project sweeps.

Bit-exactness on the board is NOT in these reports -- it comes from
tools/board_capture.py, which appends every capture to
results/board/captures.csv.
"""
import glob, os, re, csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, "..", "results", "syn")
CAP = os.path.join(HERE, "..", "results", "board", "captures.csv")
# Out-of-context Fmax from syn/fmax_sweep.tcl (results/syn/fmax_sweep.log)
OOC = {"uniform18": 66.3, "main9": 85.4}


def summary(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    i = txt.index("Design Timing Summary")
    hdr = re.search(r"WNS\(ns\).*\n\s*-+.*\n\s*(\S+)\s+\S+\s+\S+\s+\S+\s+(\S+)", txt[i:])
    return float(hdr.group(1)), float(hdr.group(2))


def main():
    runs = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(SYN, "board_*_timing.rpt"))):
        m = re.match(r"board_(.+)_(unif|lasso)_mmcm([0-9p]+)_timing\.rpt$", os.path.basename(p))
        if not m:
            continue
        tag, rom, mhz = m.group(1), m.group(2), float(m.group(3).replace("p", "."))
        wns, whs = summary(p)
        runs[(tag, rom)].append((mhz, wns, whs, wns >= 0 and whs >= 0))

    if not runs:
        raise SystemExit("no results/syn/board_*_timing.rpt found")
    print(f"{'build':22s} {'MHz':>6s} {'WNS':>8s} {'WHS':>8s}")
    best = {}
    for key, rows in runs.items():
        for mhz, wns, whs, ok in sorted(rows, reverse=True):
            print(f"{key[0]+'/'+key[1]:22s} {mhz:6.2f} {wns:8.3f} {whs:8.3f}  {'MET' if ok else 'MISS'}")
        met = [r[0] for r in rows if r[3]]
        if met:
            f = max(met)
            above = [r[0] for r in rows if not r[3] and r[0] > f]
            best[key] = (f, min(above) if above else None)

    print("\nin-context Fmax (met / first miss above it), vs out-of-context sweep:")
    for (tag, rom), (f, miss) in best.items():
        ooc = OOC.get(tag)
        print(f"  {tag:10s} {rom:5s} met {f:6.2f} MHz, missed {miss if miss else 'n/a'}"
              + (f"   OOC {ooc} MHz -> in-context is {100*(f/ooc-1):+.1f}% at the met point" if ooc else ""))

    a, b = best.get(("uniform18", "unif")), best.get(("main9", "unif"))
    if a and b and a[1] and b[1]:
        print(f"\nspeed-up in context: {100*(b[0]/a[0]-1):+.1f}% at the met points, "
              f"bracket {100*(b[0]/a[1]-1):+.1f}% to {100*(b[1]/a[0]-1):+.1f}%")

    if os.path.exists(CAP):
        print("\nboard captures (results/board/captures.csv):")
        for r in csv.DictReader(open(CAP)):
            print(f"  {r['time']}  {r['op']:4s} {r['tag']:7s} F={r['fmain']:2s}  {r['result']}")


if __name__ == "__main__":
    main()
