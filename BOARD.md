# Board bring-up — Basys3 (xc7a35tcpg236-1), 2026-09-17

## Result

Both headline builds, all three operators, **bit-exact against the golden
model on physical hardware**, verified by script over UART.

| build | F_MAIN | L1 | Box | L2 |
|---|---|---|---|---|
| uniform18 | 16 | PASS | PASS | PASS |
| main9_uniform | 9 | PASS | PASS | PASS |

Iteration count on led[11:4] matched gate-level simulation (L1 at F=16: 28).

Validation chain for the design point is now complete:
error model → bit-exact software golden → post-route gate-level (SAIF runs,
`results/syn/gl_*_xsim.log`) → physical Artix-7. The same `.mem` files are
the reference at every link.

## Session 2 result (2026-10-03) — timing-clean, at speed, LASSO on silicon

Every build: one MMCM on a BUFG, timing met in context after routing (setup
AND hold), bitstream written only then (`syn/board_build.tcl`). Every capture
bit-exact against the golden vectors over UART.

| build | clock | in-context timing | captures |
|---|---|---|---|
| main9 / LASSO (3 instances, L1 lane) | 50 MHz | met | lasso0, lasso1, lasso2 PASS |
| main9 / L1, Box, L2 | **82.5 MHz** | WNS +0.079, WHS +0.018 (85 MHz: WNS -0.356, MISS) | 3/3 PASS |
| uniform18 / L1, Box, L2 | **65 MHz** | WNS +0.281, WHS +0.025 (66.25 MHz: WNS -0.121, MISS) | 3/3 PASS |

**In-context Fmax**: main9 between 82.5 and 85 MHz (OOC sweep 85.4);
uniform18 between 65 and 66.25 MHz (OOC 66.3). The wrapper and MMCM cost
2-3.4% at the met point, about what clock jitter alone accounts for.
**Speed-up in context: +26.9% at the met points, bracket +24.5% to +30.8%**,
against +28.8% (bracket +27.6% to +30.4%) out of context. The brackets
overlap; the headline survives being measured inside a real design.
`python tools/board_table.py` regenerates all of this from the committed
timing reports.

Captures were read from the terminal this session (T, 2026-10-03);
`tools/board_capture.py` now appends every capture to
`results/board/captures.csv`, so future board evidence is a file.

**Supersedes session 1 as the paper's hardware claim.** Session 1's bitstreams
used the fabric divider behind a LUT clock mux and never met timing in
context (WNS -5.69 / WHS -2.59 when put through the same gate). Their PASS
results are functional evidence at 50 MHz; session 2 is the clean claim.

## Files

| file | role |
|---|---|
| `rtl/basys3_wrapper.v` | ROM-fed solve loop, LED status, UART results |
| `rtl/uart_tx.v` | 8N1 transmitter, 115200 baud at 50 MHz |
| `syn/basys3.xdc` | pins + divided-clock constraint |
| `syn/board_build.tcl` | scripted bitstream: ROM guards, MMCM at an exact MHz, in-context timing gate |
| `syn/board_program.tcl` | JTAG programming without the GUI |
| `tools/board_table.py` | in-context Fmax brackets and speed-up from the timing reports |
| `tb/vectors/{M,q,z}_all.mem` | ROM images: L1, Box, L2 end to end |
| `tools/make_rom.py` | regenerate the ROM images from `*_unif.mem` |
| `tools/board_capture.py` | capture UART, diff vs golden, PASS/FAIL |

## Controls

sw[0] 0 = single-shot / 1 = freerun (wall-power workload) · sw[2:1] operator
(00 L1, 01 Box, 10 L2) · sw[3] leave 0 (50 MHz) · btnC start · btnU reset.
LEDs: [0] heartbeat, [2] PASS, [3] FAIL, [11:4] iteration count,
[14] ROM failed to load (PASS suppressed), [15] UART busy.

## Procedure

1. Vivado project on part `xc7a35tcpg236-1` (or Boards → Basys3). Add `rtl/*.v`,
   `syn/basys3.xdc`, and the three `*_all.mem` **as design sources**.
2. For F_MAIN = 9: `python model/gen_vectors_cfg.py 9 9 9 9 unif`,
   `python tools/make_rom.py`, and set `-verilog_define F_MAIN=9` in synthesis
   settings. **Do not edit `admm_defs.vh`** — it stays at 16 for `build.bat`.
   Back up the F=16 vectors first; regeneration overwrites in place.
3. Program, confirm led[0] heartbeat, then
   `python tools/board_capture.py --port COMn --op l1 --fmain <F>` and press
   btnC **after** the script prints "waiting".

## Session 2 plan — LASSO on silicon, and at-speed in context

Two gaps the paper would otherwise carry: LASSO has only run in simulation,
and the board has only ever run at 50 MHz while the paper quotes 85.4 MHz
(out-of-context). Both are closed by three scripted builds. All commands from
the repo root, in a cmd window where Vivado's `settings64.bat` has been run.

Builds are scripted (`syn/board_build.tcl`): one MMCM at exactly the requested
frequency, timing checked **in context, after routing**, and no bitstream
written unless setup AND hold are met. Candidates are tried highest first.
Programming is scripted too (`syn/board_program.tcl`). Both were exercised
against a mock of the Vivado API; the wrapper itself (all three ROM slots,
LASSO_ROM, the MMCM build, and the UART frame at both baud dividers) passes
in simulation.

**Finding from the first attempt (2026-10-03).** The scripted gate refused the
original divider build at 50 MHz: WNS -5.69 ns, WHS -2.59 ns. Cause: the
bring-up clock is a fabric /2 divider behind a LUT mux with the raw 100 MHz,
so both clocks sit on the design clock net -- Vivado times the core at
100 MHz and across the two clocks, and the LUT-routed clock's skew produces
thousands of hold violations. **The session-1 GUI bitstreams had the same
structure and never met timing in context**; the GUI writes a bitstream
regardless. Their bit-exact PASS results stand as functional evidence at
50 MHz, but the paper's hardware claim should rest on the MMCM builds below,
which have one clock on a BUFG and a clean timing report. Every build now
uses the MMCM, 50 MHz included (M=6, D=12).

**Step 1 — LASSO, F_MAIN=9, 50 MHz.** One bitstream holds all three instances.

    python model/gen_vectors_cfg.py 9 9 9 9 unif
    python model/gen_vectors_lasso.py 9
    python tools/make_rom.py --lasso
    vivado -mode batch -source syn/board_build.tcl -tclargs main9 9 lasso 50
    vivado -mode batch -source syn/board_program.tcl -tclargs results/board/main9_lasso_mmcm50.bit

sw[0]=0, sw[3]=0. sw[2:1] now picks the INSTANCE (00 = m=32, 01 = m=16,
10 = m=8); the lane is L1 for all three. For each:

    python tools/board_capture.py --port COMn --op l1 --tag lasso0 --fmain 9
    python tools/board_capture.py --port COMn --op l1 --tag lasso1 --fmain 9
    python tools/board_capture.py --port COMn --op l1 --tag lasso2 --fmain 9

Expected iteration counts on led[11:4]: 11, 9, 11.

**Step 2 — main9 at speed.** You can start this build while capturing step 1:
the build copies the ROM before it starts, and the LASSO goldens are separate
files.

    python tools/make_rom.py
    vivado -mode batch -source syn/board_build.tcl -tclargs main9 9 unif 85 82.5 80 77.5 75
    vivado -mode batch -source syn/board_program.tcl -tclargs results/board/<the .bit it names>.bit

led[13] must be lit (MMCM locked). sw[2:1] = 00/01/10 for L1/Box/L2:

    python tools/board_capture.py --port COMn --op l1  --fmain 9
    python tools/board_capture.py --port COMn --op box --fmain 9
    python tools/board_capture.py --port COMn --op l2  --fmain 9

Expected iterations: 15, 19, 12.

**Step 3 — uniform18 at speed**, so the speed-up can be stated in context too.
Only after step 2's captures — this restores the F=16 vectors in place.

    git checkout -- tb/vectors
    python tools/make_rom.py
    vivado -mode batch -source syn/board_build.tcl -tclargs uniform18 16 unif 66.25 65 62.5 60
    vivado -mode batch -source syn/board_program.tcl -tclargs results/board/<the .bit it names>.bit
    (the same three captures with --fmain 16; expected iterations 28, 32, 22)

**Bring back:** the SUMMARY block each build prints, every board_capture
output, and `results/syn/board_*_timing.rpt`. The timing reports are the
in-context evidence and get committed.

**What each outcome means.** Step 1 PASS: LASSO is bit-exact on silicon, and
the paper's "unchanged hardware" claim stops resting on simulation. Steps 2-3:
the first frequency that meets timing is the in-context Fmax, bracketed by
the one above it that missed (2.5 MHz steps, coarser than the 1 MHz OOC
bracket); a PASS at that clock is bit-exactness at speed. If neither build
reaches its OOC Fmax in context, that is expected -- MMCM jitter and the
wrapper cost some margin -- and the paper reports both numbers with the
reason, not the better one.

## Bugs hit, all fixed — recorded so they are not repeated

1. **Wrong project part** — bank-34 "High Performance" / GT-terminal errors
   mean the part is not the Basys3's. Fix the part, not the pins.
2. **Missing ROM files → false PASS.** `$readmemh` could not find the `.mem`
   files, ROM synthesised to zero, the solver "converged" in 1 iteration, and
   z_out = 0 matched z_gold = 0. led[14] (`rom_bad`) now flags this.
3. **Newline delimiter in binary data.** The capture script read up to 0x0A;
   lane 2 of `z_l1_unif` is 0x3060A, so the read stopped at 6 bytes. Now reads
   a fixed length.
4. **admm_top parameter defaults.** ASYMMETRIC=1 and USE_DSP_L2=1 by default.
   The wrapper built lanes 16/8/7: L1 passed by luck (its lane is unchanged),
   Box returned values that were exact multiples of 256 and ran 23 iterations —
   the `asym_nodsp` count. Parameters now passed explicitly.

## Not done

**Wall power — DROPPED 2026-09-20 (T's call).** Needs a bench supply on the barrel jack (JP2 = WALL) or a meter
with ≤1 mA resolution. The build-to-build difference is ~4 mW core dynamic
against a board draw of hundreds of mW, so it is likely below the floor of
available instruments. The feasible and still useful measurement is idle
(btnU held) vs freerun on the SAME bitstream. If the build comparison cannot
be resolved, report it as below the measurement floor — the SAIF figures stand
on their own.
