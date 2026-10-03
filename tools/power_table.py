#!/usr/bin/env python3
"""power_table.py -- every SAIF power measurement, with its provenance.

    python tools/power_table.py

Reads results/syn/<tag>_power_saif.rpt. Refuses to print any build whose
Vivado confidence is not High, because a vectorless fallback reports the same
fields and looks identical. Marks which tags syn/run_ooc.tcl can still
rebuild: a number from a tag the script cannot reproduce violates the
project's one-scripted-pass rule and must be labelled legacy in the paper.
"""
import os, re, glob, json

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, "..", "results", "syn")
OOC = os.path.join(HERE, "..", "syn", "run_ooc.tcl")

buildable = set(re.findall(r"^\s{4}(\w+)\s+\d", open(OOC).read(), re.M))

rows = []
for p in sorted(glob.glob(os.path.join(SYN, "*_power_saif.rpt"))):
    tag = os.path.basename(p)[:-len("_power_saif.rpt")]
    txt = open(p, encoding="utf-8", errors="replace").read()
    g = lambda n: re.search(rf"\|\s*{re.escape(n)}\s*\|\s*([0-9.]+|\w+)\s*\|", txt)
    dyn, tot = float(g("Dynamic (W)").group(1)), float(g("Total On-Chip Power (W)").group(1))
    conf = g("Confidence Level").group(1)
    m = re.search(r"Design Nets Matched\s*\|\s*([0-9]+%\s*\([0-9/]+\))", txt)
    rows.append(dict(tag=tag, dyn_mw=round(dyn * 1000), total_mw=round(tot * 1000),
                     confidence=conf, rebuildable=tag in buildable,
                     nets_matched=re.sub(r"\s+", "", m.group(1)) if m else "n/r"))

bad = [r["tag"] for r in rows if r["confidence"] != "High"]
if bad:
    raise SystemExit(f"confidence not High: {bad} -- these are vectorless, do not quote")

print(f"{'tag':18s} {'dyn':>5s} {'total':>6s} {'conf':>5s} {'nets':>14s}  rebuildable")
for r in rows:
    print(f"{r['tag']:18s} {r['dyn_mw']:4d}m {r['total_mw']:5d}m {r['confidence']:>5s} "
          f"{r['nets_matched']:>14s}  {'yes' if r['rebuildable'] else 'NO -- legacy tag'}")

pairs = [("uniform10", "asym_derived", "F_MAIN=16, lanes 8"),
         ("main9_uniform", "main9_asym", "F_MAIN=9"),
         ("uniform_nodsp", "asym_nodsp", "F_MAIN=16, legacy tags")]
d = {r["tag"]: r for r in rows}
print("\nasymmetry null pairs (uniform vs asymmetric at the same F_MAIN):")
for a, b, what in pairs:
    if a in d and b in d:
        mark = "" if (d[a]["rebuildable"] and d[b]["rebuildable"]) else "   [LEGACY]"
        print(f"  {what:24s} {d[a]['dyn_mw']:2d} mW vs {d[b]['dyn_mw']:2d} mW"
              f"  delta {d[b]['dyn_mw']-d[a]['dyn_mw']:+d} mW{mark}")
print("  Reports round to 1 mW, so each pair resolves a difference no finer than that.")

json.dump(rows, open(os.path.join(SYN, "..", "power_table.json"), "w"), indent=1)
