#!/usr/bin/env python3
"""make_rom.py -- build the concatenated ROM images basys3_wrapper reads.

    python tools/make_rom.py            # from tb/vectors/*_unif.mem
    python tools/make_rom.py --l1 lasso1   # L1 slot <- l1_lasso1 (LASSO run)

The wrapper holds one flat ROM per quantity with the three operator sets laid
end to end in the order L1, Box, L2, selected by sw[2:1]. Regenerate these
whenever the vectors change -- especially after gen_vectors_cfg.py, because
the ROM must be at the SAME F_MAIN as the synthesised design or the board
mismatches for the wrong reason.
"""
import argparse, os
ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="unif")
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--l1", default=None,
                help="tag for the L1 slot only, e.g. lasso1 (gen_vectors_lasso.py)")
a = ap.parse_args()
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tb", "vectors")
for kind, per in (("M", a.n * a.n), ("q", a.n), ("z", a.n)):
    out = []
    for op in ("l1", "box", "l2"):
        tag = a.l1 if (op == "l1" and a.l1) else a.tag
        p = os.path.join(here, f"{kind}_{op}_{tag}.mem")
        lines = [l.strip() for l in open(p) if l.strip()]
        if len(lines) != per:
            raise SystemExit(f"{p}: {len(lines)} words, expected {per}")
        out += lines
    if len({len(l) for l in out}) != 1:     # mixed F_MAIN across slots
        raise SystemExit(f"{kind}: slots have different word widths "
                         f"{sorted({len(l) for l in out})} -- regenerate all "
                         "three at the same F_MAIN before building the ROM")
    dst = os.path.join(here, f"{kind}_all.mem")
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"wrote {kind}_all.mem  {len(out)} words x {len(out[0])*4} bits")
