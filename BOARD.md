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

## Files

| file | role |
|---|---|
| `rtl/basys3_wrapper.v` | ROM-fed solve loop, LED status, UART results |
| `rtl/uart_tx.v` | 8N1 transmitter, 115200 baud at 50 MHz |
| `syn/basys3.xdc` | pins + divided-clock constraint |
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

## LASSO on the board (optional, F_MAIN = 9)

The RTL is already bit-exact on LASSO at F=9 in simulation; this adds the
hardware link. The ROM holds one set per operator, so LASSO goes in the L1 slot.

1. `python model/gen_vectors_cfg.py 9 9 9 9 unif` (Box/L2 slots at F=9)
2. `python model/gen_vectors_lasso.py 9`
3. `python tools/make_rom.py --l1 lasso1` (m=16 instance; `lasso0` m=32,
   `lasso2` m=8). It refuses if the slots are at different widths.
4. Synthesise with `-verilog_define F_MAIN=9`, program, sw[2:1]=00, then
   `python tools/board_capture.py --port COMn --op l1 --tag lasso1 --fmain 9`.
5. Afterwards restore F=16: `python model/gen_vectors_cfg.py 16 16 16 16 unif`,
   `python model/gen_vectors_lasso.py 16`, `python tools/make_rom.py`.

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

**Wall power.** Needs a bench supply on the barrel jack (JP2 = WALL) or a meter
with ≤1 mA resolution. The build-to-build difference is ~4 mW core dynamic
against a board draw of hundreds of mW, so it is likely below the floor of
available instruments. The feasible and still useful measurement is idle
(btnU held) vs freerun on the SAME bitstream. If the build comparison cannot
be resolved, report it as below the measurement floor — the SAIF figures stand
on their own.
