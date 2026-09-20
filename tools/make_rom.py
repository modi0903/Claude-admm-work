#!/usr/bin/env python3
"""make_rom.py -- build the concatenated ROM images basys3_wrapper reads.

    python tools/make_rom.py            # from tb/vectors/*_unif.mem

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
a = ap.parse_args()
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tb", "vectors")
for kind, per in (("M", a.n * a.n), ("q", a.n), ("z", a.n)):
    out = []
    for op in ("l1", "box", "l2"):
        p = os.path.join(here, f"{kind}_{op}_{a.tag}.mem")
        lines = [l.strip() for l in open(p) if l.strip()]
        if len(lines) != per:
            raise SystemExit(f"{p}: {len(lines)} words, expected {per}")
        out += lines
    dst = os.path.join(here, f"{kind}_all.mem")
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"wrote {kind}_all.mem  {len(out)} words x {len(out[0])*4} bits")
