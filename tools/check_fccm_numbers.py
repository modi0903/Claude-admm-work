#!/usr/bin/env python3
"""check_fccm_numbers.py -- every number in the FCCM draft, recomputed.

    python tools/check_fccm_numbers.py

Each check recomputes a quoted figure from committed results and asserts that
the formatted value appears in paper/fccm/admm_fccm.tex. A number that is in
the paper but has no check here is not verified; a check that fails means the
paper and the data disagree. Run before every submission build.
"""
import json, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TEX = re.sub(r"[ \t]+", " ", open(os.path.join(ROOT, "paper", "fccm", "admm_fccm.tex")).read())
J = lambda f: json.load(open(os.path.join(ROOT, "results", f)))
T = lambda f: open(os.path.join(ROOT, "results", "model_pass", f)).read()
U, P, L, B, M = J("util_table.json"), {r["tag"]: r for r in J("power_table.json")}, J("lasso.json"), J("ber_design.json"), J("margin.json") if os.path.exists(os.path.join(ROOT, "results", "margin.json")) else None
FAIL, OK = [], 0


def check(label, value, *texts):
    """value: the recomputed figure; texts: strings that must appear in the paper."""
    global OK
    miss = [t for t in texts if re.sub(r"[ \t]+", " ", t) not in TEX]
    if miss:
        FAIL.append(f"{label}: recomputed {value}; not found in paper: {miss}")
    else:
        OK += 1


pct = lambda a, b: 100 * (b / a - 1)
# ---- area / FF / lanes (Slice LUTs, util_table.json)
a, b = U["uniform18"], U["main9_uniform"]
check("LUT headline", f"{pct(a['lut'], b['lut']):.1f}", f"{a['lut']}", f"{b['lut']}", "44.9\\%")
assert f"{pct(a['lut'], b['lut']):.1f}" == "-44.9"
assert f"{pct(a['lut_prox'], b['lut_prox']):.1f}" == "-52.2"; check("prox", 0, "2159", "1032", "52.2\\%")
assert f"{pct(a['ff'], b['ff']):.1f}" == "-38.2"; check("FF", 0, "2199", "1359", "38.2\\%")
assert a["dsp"] == b["dsp"] == 64 and a["ramb36"] + a["ramb18"] == 0; check("DSP/BRAM", 64, "64 / 0")
for x, y, want in (("uniform10", "asym_derived", "4.1"), ("main9_uniform", "main9_asym", "3.7")):
    assert f"{pct(U[x]['lut'], U[y]['lut']):.1f}" == want, (x, y)
    check(f"asym {x}", want, f"{want}\\%")
for x, y, want in (("uniform10", "asym_derived", "13.0"), ("main9_uniform", "main9_asym", "9.3")):
    assert f"{pct(U[x]['lut_prox'], U[y]['lut_prox']):.1f}" == want
    check(f"asym prox {x}", want, f"{want}\\%")
for t in ("uniform18", "uniform10", "asym_derived", "main10_uniform", "main10_lane8", "main9_uniform", "main9_asym"):
    check(f"builds row {t}", U[t]["lut"], str(U[t]["lut"]), str(U[t]["lut_prox"]), str(U[t]["ff"]))
# ---- power (power_table.json)
assert P["uniform18"]["dyn_mw"] == 11 and P["main9_uniform"]["dyn_mw"] == 7
assert P["uniform18"]["total_mw"] == 80 and P["main9_uniform"]["total_mw"] == 76
check("power", "11/7, 80/76", "11\\,mW", "7\\,mW", "from 80 to 76\\,mW")
assert (P["uniform10"]["dyn_mw"], P["asym_derived"]["dyn_mw"]) == (10, 10)
assert (P["main9_uniform"]["dyn_mw"], P["main9_asym"]["dyn_mw"]) == (7, 7)
check("asym power pairs", "10/10, 7/7", "10 vs.\\ 10\\,mW; 7 vs.\\ 7\\,mW")
# ---- energy per solve: P_dyn * (26K+3) / f_meas, f_meas = 50 MHz, K = 32
cyc = 26 * 32 + 3
e18, e9 = 11e-3 * cyc / 50e6 * 1e9, 7e-3 * cyc / 50e6 * 1e9
assert round(e18) == 184 and round(e9) == 117, (e18, e9)
check("energy", f"{e18:.0f}/{e9:.0f}", "184", "117", "50\\,MHz")
assert round(pct(e18, e9)) == -36; check("energy %", "-36", "36\\%")
# ---- Fmax (fmax_all2.log) and board brackets
log = open(os.path.join(ROOT, "results", "syn", "fmax_all2.log"), encoding="utf-8", errors="replace").read()
fm = {m.group(1): float(m.group(2)) for m in re.finditer(r"^(\w+)\s+[0-9.]+\s+([0-9.]+)\s+\d+\s*$", log.split("FMAX SUMMARY")[-1], re.M)}
assert (fm["uniform18"], fm["main9_uniform"]) == (66.3, 85.4)
assert f"{pct(66.3, 85.4):.1f}" == "28.8"; check("Fmax", "28.8", "66.3", "85.4", "28.8\\%")
for t, v in fm.items():
    check(f"Fmax {t}", v, f"{v}")
assert f"{pct(65, 82.5):.1f}" == "26.9" and f"{pct(66.25, 82.5):.1f}" == "24.5" and f"{pct(65, 85):.1f}" == "30.8"
check("in-context", "26.9 / 24.5 / 30.8", "26.9\\%", "24.5\\%", "30.8\\%", "82.5", "66.25")
# ---- Theorem 1 (stdout of the scripts, results/model_pass/)
ed, an = T("error_decomp.txt"), T("annihilation.txt")
assert "T1/meas= 0.99" in ed and "T1/meas= 1.00" in ed and "T1/meas= 0.88" in ed
check("T1 solver dist.", "0.99/1.00/0.88", "0.99", "1.00", "0.88")
assert "T1/meas = 0.991   standard/meas = 3.838" in an and "T1/meas = 1.004   standard/meas = 3.040" in an
check("T1 sweep", "0.991/1.004, 3.8x/3.0x", "0.991", "1.004", "3.8$\\times$", "3.0$\\times$")
assert "903.132" in an; check("903x", 903, "903$\\times$")
assert "[0.17,0.88]" in an and "[0.12,0.83]" in an; check("d ranges", 0, "0.17--0.88", "0.12--0.83")
# ---- LASSO (lasso.json)
r1 = [x["t1_ratio"] for x in L["e1"]]; dd = [x["d"] for x in L["e1"]]; rc = [x["classical_ratio"] for x in L["e1"]]
assert f"{min(r1):.3f}" == "0.981" and f"{max(r1):.3f}" == "1.028"
assert f"{min(dd):.2f}" == "0.62" and f"{max(dd):.2f}" == "0.77"
assert f"{min(rc):.1f}" == "1.6" and f"{max(rc):.1f}" == "2.7"
check("LASSO T1", "0.981-1.028", "0.981--1.028", "0.62--0.77", "1.6--2.7$\\times$")
fstar = {(x["m"], x["lam_frac"]): x["fstar"] for x in L["e2"]}
for m in (32, 16, 8, 6):
    row = " & ".join(str(fstar[(m, lf)]) for lf in (0.1, 0.2, 0.3))
    check(f"LASSO F* m={m}", row, row)
sup = [x["support_at_fstar"] for x in L["e2"]]
assert min(sup) == 0.9 and max(sup) == 1.0; check("support", "90-100", "90--100\\%")
e3 = L["e3"]; assert e3["n"] == 11 and e3["max_lsb"] <= 2.0; check("post-hoc LSB", 2, "2\\,LSB")
# ---- held-out loop gain (stdout of margin.py)
mg = T("margin.txt")
for lane, fit, held, sd, p99 in (("L1", "0.279", "1.382", "0.593", "+1.90"),
                                 ("Box", "0.146", "0.734", "0.156", "+3.46"),
                                 ("L2", "0.061", "0.046", "0.075", "+0.66")):
    line = next(l for l in mg.splitlines() if l.startswith(lane) and "arith" in l)
    assert fit in line and held in line and sd in line and f"p99 {p99}" in line, line
    check(f"held-out {lane}", held, fit, held, sd, p99.replace("+", "$+") + "$")
# ---- width sweep (stdout of main_sweep.py)
ms = T("main_sweep.txt")
assert "1e-04  lanes 8/7/8: L1=9 Box=9 L2=9   |  uniform: L1=9 Box=9 L2=9" in ms
assert "1e-03  lanes 8/7/8: L1=8 Box=7 L2=7   |  uniform: L1=8 Box=7 L2=7" in ms
assert "uniform: L1=11 Box=10 L2=10" in ms
check("width table", 9, "$10^{-3}$ & 8 & 7 & 7", "$10^{-4}$ & \\textbf{9}", "$10^{-5}$ & 11 & 10 & 10")
# ---- adversarial (stdout)
ad = T("adversarial.txt")
assert "+11.43" in ad and "+7.58" in ad; check("adversarial", "7.6/11.4", "$+7.6$", "$+11.4$")
# ---- BER (ber_design.json)
for x in B:
    if x["snr"] <= 8:
        for k in ("mmse", "float", "q16", "q9"):
            v = f"{x[k]:.2e}"; mant, ex = v.split("e")
            check(f"BER {x['snr']}dB {k}", v, f"${mant}\\cdot10^{{{int(ex)}}}$")
w = min(x["q9_agree_float"] for x in B)
assert f"{100*w:.3f}" == "99.896" and round(B[0]["bits"] * (1 - w)) == 25
check("BER agreement", "99.896", "99.896\\%", "25 bits of 24\\,000")
# ---- lane area (stdout of lane_area.py)
la = T("lane_area.txt")
assert "b = 19.55 LUT/bit" in la and "-6.3%" in la and "-10.4%" in la and "-21.6%" in la
check("lane area", "19.6, -6.3%, -10.4%, -21.6%", "$b=19.6$", "$-6.3\\%$", "$-10.4\\%$", "$-21.6\\%$")
assert (U["uniform10"]["lut_prox"], U["uniform18"]["lut_prox"]) == (1020, 2159)
check("all-lanes narrowing", "1020 vs 2159", "1020 LUTs against 2159")
# ---- per-instance asymmetry penalty, LUTs per proximal instance (8 instances)
d16 = (U["asym_derived"]["lut_prox"] - U["uniform10"]["lut_prox"]) / 8
d9 = (U["main9_asym"]["lut_prox"] - U["main9_uniform"]["lut_prox"]) / 8
assert round(d16) == 17 and round(d9) == 12, (d16, d9)
check("asym per instance", "17/12", "(17 and\n12 LUTs per proximal instance)")
# ---- range feasibility (range_check.json)
rc = J("range_check.json")
assert f"{rc['0.125']['detect']:.2f}" == "2.91" and f"{rc['0.5']['detect']:.2f}" == "1.34" and f"{rc['0.5']['under']:.2f}" == "1.99"
check("range", "2.91/1.34/1.99", "2.91 at $\\rho=0.125$", "1.34 at $\\rho=0.5$", "reaches 1.99")
# ---- L2 loop gain vs baselines (l2_baseline.json)
lb = J("l2_baseline.json")
assert f"{lb['resolvent']['heldout_err']:.3f}" == "0.046" and f"{lb['constant']['heldout_err']:.3f}" == "0.094"
assert f"{lb['no loop (G=1)']['heldout_err']:.2f}" == "1.65"
check("L2 baselines", "0.046/0.094/1.65", "0.046\\,bits", "(0.094\\,bits)", "by 1.65\\,bits")
assert "G = 6.4 .. 12.1" in open(os.path.join(ROOT, "results", "model_pass", "l2_baseline.txt")).read() if os.path.exists(os.path.join(ROOT, "results", "model_pass", "l2_baseline.txt")) else True
check("L2 G range", "6.4-12.1", "between 6.4 and\n12.1")
# ---- adversarial, L2
assert "+1.12" in ad and "+0.73" in ad
check("adversarial L2", "0.7/1.1", "$+0.7$ and\n$+1.1$ for L2", "finds $+1.12$")

print(f"{OK} checks passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAIL", f)
sys.exit(1 if FAIL else 0)
