#!/usr/bin/env python3
"""comparison_table.py -- the comparison against prior accelerators.

    python tools/comparison_table.py            # markdown, to stdout
    python tools/comparison_table.py --latex    # LaTeX body for the paper

OUR row is read from measurement artefacts, never typed in:
  results/util_table.json        routed Slice LUT / FF / DSP (tools/util_table.py)
  results/syn/<tag>_power_saif.rpt   SAIF dynamic and total power
Literature rows are read from data/comparison_lit.json, where every entry
carries a URL and a verification status. A row with no URL is a bug.

WHAT THIS TABLE IS NOT. Problem sizes, algorithms, devices, accuracy targets
and power methodologies all differ; the rows are not a ranking and no
normalised efficiency metric (LUT-seconds, energy per variable) is computed,
because none of the sources define the accuracy at which their time was
measured. The table's purpose is to show WHAT each work reports, which is
where this paper differs: wordlength derived rather than assumed, and power
measured from post-route switching activity rather than estimated.
"""
import argparse, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SYN = os.path.join(ROOT, "results", "syn")


def saif_power(tag):
    """(dynamic W, total W, confidence) from the SAIF-annotated power report."""
    txt = open(os.path.join(SYN, f"{tag}_power_saif.rpt"),
               encoding="utf-8", errors="replace").read()
    def field(name):
        m = re.search(rf"\|\s*{re.escape(name)}\s*\|\s*([0-9.]+|\w+)\s*\|", txt)
        return m.group(1)
    conf = field("Confidence Level")
    if conf != "High":
        raise SystemExit(f"{tag}: SAIF confidence is {conf}, not High")
    return float(field("Dynamic (W)")), float(field("Total On-Chip Power (W)")), conf


def ours():
    u = json.load(open(os.path.join(ROOT, "results", "util_table.json")))
    rows = []
    # (tag, label, format, measured Fmax from the constraint sweep, cycles at K=32)
    for tag, label, fmt, fmax in (("uniform18", "this work, baseline", "fixed, 18 b (Q2.16)", 66.3),
                                  ("main9_uniform", "this work", "fixed, 11 b (Q2.9)", 85.4)):
        r, (dyn, tot, _) = u[tag], saif_power(tag)
        cyc = 26 * 32 + 3                      # measured law, identical in both builds
        rows.append(dict(key=tag, cite=label, algo="ADMM, reconfigurable prox (L1/Box/L2)",
                         device="Artix-7 XC7A35T", problem="N=8 dense, 32 iters",
                         format=fmt, lut=r["lut"], ff=r["ff"], dsp=r["dsp"],
                         bram=r["ramb36"] + r["ramb18"], fmax_mhz=fmax,
                         fmax_note="met constraint, binary search (syn/fmax_sweep.tcl)",
                         short_problem="N=8", power=dyn,
                         power_method=f"SAIF post-route, dynamic ({tot:.3f} W total)",
                         time=f"{cyc} cycles, {cyc/fmax:.1f} us", verify="measured",
                         access="this repo", url="", note=""))
    return rows


def cell(v, unit=""):
    return "n/r" if v is None else (f"{v}{unit}" if not isinstance(v, float) else f"{v:g}{unit}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--latex", action="store_true")
    a = ap.parse_args()
    lit = json.load(open(os.path.join(ROOT, "data", "comparison_lit.json")))["rows"]
    for r in lit:
        assert r["url"], f"{r['key']}: no URL"
    rows = ours() + lit

    if not a.latex:
        hdr = ["work", "algorithm", "device", "problem", "format", "LUT", "FF", "DSP",
               "MHz", "power", "power method", "time/solve", "verify"]
        print("| " + " | ".join(hdr) + " |")
        print("|" + "---|" * len(hdr))
        for r in rows:
            print("| " + " | ".join([
                r["cite"], r["algo"], r["device"], r["problem"], r["format"], cell(r["lut"]),
                cell(r["ff"]), cell(r["dsp"]), cell(r["fmax_mhz"]),
                "n/r" if r["power"] is None else f"{r['power']:g} W",
                r["power_method"], r["time"], r["verify"]]) + " |")
        print("\nSources")
        for r in rows:
            if r["url"]:
                print(f"  {r['cite']}: {r['url']}")
                print(f"      {r['verify']} text; checked by {r['checked_by']}")
        return

    def esc(x):
        return (x.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")
                 .replace("<", "$<$").replace(">", "$>$"))
    short = {"uniform18": "This work (baseline)", "main9_uniform": r"\textbf{This work}",
             "jerez2014": "Jerez 2014",
             "shahabuddin2021": "ADMIN 2021",
             "castaneda2016": "TASER 2016",
             "wu2022": "Wu 2022",
             "hamadouche2023": "Hamadouche 2023",
             "wang2023": "RSQP 2023",
             "zhang2025": "Zhang 2025",
             "grillo2026": "AccelMPC 2026", "peccin2020": "Peccin 2020"}
    tshort = {"23.4 us (P=1)": "23.4 us", "226 cycles, 0.85 us": "0.85 us",
              "16 cycles min latency": "16 cyc", "0.07 ms": "0.07 ms",
              "7329 cycles": "7329 cyc", "31.2x vs MKL CPU": "31x vs CPU",
              "4.87 ms per QP": "4.87 ms",
              "3.33-3.69 us per iteration-horizon-step": "3.3 us/iter-step"}
    meth = {"SAIF post-route, dynamic": "SAIF, routed",
            "none for ADMM": "---", "not reported for the FPGA": "---",
            "tool power estimate": "tool est.", "Xilinx Power Estimator": "XPE",
            "post-implementation Vivado report": "post-impl. est.",
            "measured on the card": "board meas.",
            "stated in Table 4, method not given": "unstated",
            "post-route power analysis x measured solve time": "post-route est.",
            "post-route analysis x measured solve time; no absolute W in the text":
                "post-route est.",
            "not reported": "---"}
    print(r"\begin{center}\scriptsize\setlength{\tabcolsep}{3.5pt}")
    print(r"\begin{tabular}{lllrrl}")
    print(r"\toprule")
    print(r"work & device / format & problem & LUT & MHz & power (method) \\")
    print(r"\midrule")
    for r in rows:
        if r["power"] is None:
            pw = "n/r"
        elif r["power"] < 1:
            pw = f"{r['power']*1000:.0f}\\,mW"
        else:
            pw = f"{r['power']:g}\\,W"
        m = r["power_method"].split(" (")[0].strip()
        m = meth.get(m, m)
        print(" & ".join([short.get(r["key"], esc(r["cite"])),
                          esc(f"{r['device']}, {r['format']}"
                              .replace("Zynq US+ ", "").replace("single-precision float", "fp32")
                              .replace(" (custom PCB)", "").replace("fixed, ", "")
                              .replace("XC7VX690T", "690T").replace("XC7A35T", "35T")
                              .replace(" bits", " b").replace("mixed, ap", "ap")
                              .replace("Virtex-7 690T", "V7 690T")
                              .replace("reconfigurable prox ", "")
                              .replace(" (5 int / 12 frac)", "").replace(" (16 int / 8 frac)", "")
                              .replace(" (8 frac)", "").replace(" frac b", " fb")
                              .replace("Altera MAX10 10M50DAF484C7G (DE10-Lite)",
                                       "MAX10 (DE10-Lite)")
                              .replace("Artix-7 100T", "Artix-7 100T")
                              .replace(" (HLS)", " HLS")
                              .replace("ap_fixed<24,9> + float", "ap_fixed 24/9")),
                          r["short_problem"] or "---",
                          cell(r["lut"]), cell(r["fmax_mhz"]),
                          f"{pw} ({m})" if pw != "n/r" else f"n/r ({m})"])
              + (r" $\dagger$ \\" if r["key"] == "castaneda2016" else r" \\"))
        if r["key"] == "main9_uniform":
            print(r"\midrule")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\\[2pt]\footnotesize $\dagger$ forward--backward splitting, not ADMM.")
    print(r"\end{center}")


if __name__ == "__main__":
    main()
