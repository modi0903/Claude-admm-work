#!/usr/bin/env python3
"""model_pass.py -- every model-side number in the paper, regenerated in one run.

    python tools/model_pass.py            # run everything, then compare
    python tools/model_pass.py --check    # compare only (after a run)

Runs each analysis script in dependency order. stdout of every script is kept
in results/model_pass/<script>.txt -- several headline numbers (Theorem 1's
0.99/1.00, the lattice rule's 1 bit, F*=9) are printed rather than written to
JSON, and a printed number with no stored output is a number nobody can check.

Then compares every results/*.json and tb/vectors/*.mem against the committed
version (git HEAD). Exact match is expected: every script is seeded. Any
difference is drift, and the paper must not be drafted on top of it.
"""
import json, os, subprocess, sys, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "results", "model_pass")
PY = sys.executable

# (script, args). Order matters where one script reads another's output.
RUNS = [
    ("model/error_decomp.py", []),          # T1
    ("model/annihilation.py", []),          # (1-d) mechanism
    ("model/lattice_rule.py", []),          # lattice rule, 1 bit
    ("model/main_sweep.py", []),            # F* = 9 design point
    ("model/experiments.py", []),
    ("model/generalize.py", []),
    ("model/loop_gain.py", []),
    ("model/loop_gain_l1.py", []),
    ("model/margin.py", []),                # held-out test
    ("model/box_form.py", []),
    ("model/adversarial.py", []),
    ("model/sweep_ordering.py", []),
    ("model/t2_crossover.py", []),
    ("model/kappa_term.py", []),            # reads t2_crossover.json
    ("model/lasso.py", []),
    ("model/lasso.py", ["--e3"]),           # post-hoc, reads lasso.json
    ("model/lane_area.py", []),             # reads util_table.json
    ("model/ber_design.py", []),            # design-point BER
    ("model/l2_baseline.py", []),           # L2 loop model vs constant
    ("model/range_check.py", []),           # Proposition 1
    ("model/gen_vectors.py", []),           # golden vectors, F=16
    ("model/gen_vectors_lasso.py", ["16"]),
    ("tools/make_rom.py", []),
]


def run_all():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for script, args in RUNS:
        name = os.path.basename(script)[:-3] + ("_" + "_".join(a.strip("-") for a in args) if args else "")
        t = time.time()
        p = subprocess.run([PY, script] + args, cwd=ROOT, capture_output=True, text=True)
        dt = time.time() - t
        open(os.path.join(OUT, name + ".txt"), "w").write(p.stdout + ("\n--- stderr ---\n" + p.stderr if p.stderr.strip() else ""))
        rows.append((name, p.returncode, dt))
        print(f"  {name:28s} rc={p.returncode}  {dt:7.1f} s", flush=True)
    return rows


def git_show(path):
    p = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def diff_json(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'new' if k in b else 'committed'}")
            else:
                out += diff_json(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_json(x, y, f"{path}[{i}]")
    elif a != b:
        out.append(f"{path}: {a!r} -> {b!r}")
    return out


def check():
    files = sorted(subprocess.run(["git", "ls-files", "results/*.json", "tb/vectors/*.mem"],
                                  cwd=ROOT, capture_output=True, text=True).stdout.split())
    drift = 0
    for f in files:
        old, new = git_show(f), open(os.path.join(ROOT, f)).read()
        if old is None or old == new:
            continue
        if f.endswith(".json"):
            d = diff_json(json.loads(old), json.loads(new))
            if not d:
                continue          # same values, formatting only
            drift += 1
            print(f"  DRIFT {f}: {len(d)} values")
            for line in d[:6]:
                print(f"        {line}")
        else:
            drift += 1
            print(f"  DRIFT {f}")
    print(f"\n{len(files)} committed outputs compared, {drift} drifted"
          + ("  -- all reproduce exactly" if not drift else ""))
    return drift


if __name__ == "__main__":
    if "--check" not in sys.argv:
        print("model pass: running every analysis script\n")
        rows = run_all()
        bad = [r for r in rows if r[1] != 0]
        if bad:
            print(f"\nFAILED: {[r[0] for r in bad]}")
        print()
    sys.exit(1 if check() else 0)
