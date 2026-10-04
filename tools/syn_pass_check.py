#!/usr/bin/env python3
"""syn_pass_check.py -- did a fresh run_ooc.tcl reproduce the committed builds?

    vivado -mode batch -source syn/run_ooc.tcl -nojournal -log results/syn/run_ooc_pass.log
    python tools/syn_pass_check.py

For each study build, compares the freshly written routed reports against the
committed ones (git HEAD): Slice LUT / FF / DSP / BRAM from the hierarchical
utilisation report, and WNS / WHS from the timing summary at the 20 ns
constraint.

WHY THIS IS ENOUGH. The Fmax sweep has already been run twice in full
(results/syn/fmax_all.log, fmax_all2.log) and agrees to the LUT, and the SAIF
measurement of uniform18 was repeated with an identical result. So Vivado on
this machine is deterministic. If the seven 20 ns builds also reproduce
exactly, the RTL has not drifted since those measurements and every
hardware number in the paper stands as produced by the committed scripts.
Any difference means drift, and the full pass (sweep + SAIF) must be rerun.
"""
import os, re, subprocess

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OOC = open(os.path.join(ROOT, "syn", "run_ooc.tcl")).read()
TAGS = re.findall(r"^\s{4}(\w+)\s+\d", OOC, re.M)


def util(txt):
    top = next(l for l in txt.splitlines() if l.startswith("| admm_top"))
    c = [x.strip() for x in top.strip().strip("|").split("|")]
    return dict(lut=int(c[2]), ff=int(c[6]), bram=int(c[7]) + int(c[8]), dsp=int(c[9]))


def timing(txt):
    i = txt.index("Design Timing Summary")
    m = re.search(r"WNS\(ns\).*\n\s*-+.*\n\s*(\S+)\s+\S+\s+\S+\s+\S+\s+(\S+)", txt[i:])
    return dict(wns=float(m.group(1)), whs=float(m.group(2)))


def head(path):
    p = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def main():
    bad = 0
    print(f"{'build':16s} {'LUT':>11s} {'FF':>11s} {'DSP':>7s} {'WNS@20ns':>15s}  verdict")
    for t in TAGS:
        fu, ft = f"results/syn/{t}_util_route.rpt", f"results/syn/{t}_timing_route.rpt"
        ou, ot = head(fu), head(ft)
        if ou is None or ot is None:
            print(f"{t:16s} no committed baseline"); bad += 1; continue
        new_u = util(open(os.path.join(ROOT, fu), encoding="utf-8", errors="replace").read())
        new_t = timing(open(os.path.join(ROOT, ft), encoding="utf-8", errors="replace").read())
        old_u, old_t = util(ou), timing(ot)
        same = new_u == old_u and new_t == old_t
        bad += not same
        f = lambda o, n: f"{o}" if o == n else f"{o}->{n}"
        print(f"{t:16s} {f(old_u['lut'], new_u['lut']):>11s} {f(old_u['ff'], new_u['ff']):>11s} "
              f"{f(old_u['dsp'], new_u['dsp']):>7s} {f(old_t['wns'], new_t['wns']):>15s}  "
              + ("same" if same else "**DRIFT**"))
    print("\nall seven builds reproduce exactly: the committed hardware numbers stand"
          if not bad else f"\n{bad} build(s) drifted: run the full pass (fmax sweep + SAIF) before drafting")
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
