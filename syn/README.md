# syn/ — synthesis, power and timing flow

Run order for a full measured pass (Vivado 2025.2, Windows, from the repo root):

1. `vivado -mode batch -source syn/run_ooc.tcl` — the seven study builds,
   out-of-context, routed, with utilisation/timing/power reports per tag.
2. `set SWEEP_ALL=1 && vivado -mode batch -source syn/fmax_sweep.tcl` — binary
   search on the clock constraint. Fmax is 1000/(tightest period that MET),
   never 1000/(period - slack).
3. `syn/saif_power.bat <tag> <F_MAIN> <ASYM>` — gate-level simulation of the
   regression vectors, SAIF capture, then activity-annotated `report_power`.
4. `python tools/power_table.py` / `tools/util_table.py` /
   `tools/comparison_table.py` — the numbers that reach the paper.

## Traps that cost a day each. Do not rediscover them.

- **Tcl eats backslashes.** Forward slashes in every tool argument, always.
- **A `.bat` calling a `.bat` needs `call`**, or the outer script exits.
- **xelab needs `-debug typical`** or `log_saif` silently records nothing.
- **Never `log_saif /*`.** Log the DUT instance only.
- **`-generic_top` escapes the top-level name** and corrupts the SAIF instance
  paths, so `report_power` matches 0% of nets and silently falls back to
  vectorless. Pass configuration as quoted `-d "FM=9"` macros instead.
- **Check the SAIF file size** before reading it. An empty SAIF plus a
  vectorless fallback produces a confident, wrong, ~10x-high power number.
  `tools/power_table.py` refuses any report whose confidence is not High.
- **`$sformatf` is not Verilog-2001.** Pass literal paths to the testbench.
