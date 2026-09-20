@echo off
REM =====================================================================
REM  measure_rest.bat -- SAIF power for the four builds that still carry
REM  vectorless estimates. Run from the repo root with Vivado on PATH:
REM
REM      C:\AMDDesignTools\2025.2\Vivado\settings64.bat
REM      cd /d "C:\College\Senorita\admm_project"
REM      syn\measure_rest.bat
REM
REM  ~20 min per build, ~80 min total, unattended.
REM
REM  Lane widths come from run_ooc.tcl's build list and are passed
REM  EXPLICITLY, because F_L1_P/F_BOX_P/F_L2_P override the ASYMMETRIC
REM  preset. asym_derived (8/7/8) and main9_asym (9/8/9) do NOT match the
REM  committed _asym vectors (16/8/7); using those would fail the run for
REM  the wrong reason.
REM
REM              tag              FM ASYM  FL1 FBOX FL2
REM =====================================================================
call syn\saif_power.bat uniform10       16  0    8   8    8
call syn\saif_power.bat asym_derived    16  1    8   7    8
call syn\saif_power.bat main10_uniform  10  0   10  10   10
call syn\saif_power.bat main9_asym       9  1    9   8    9
call syn\saif_power.bat main10_lane8    10  0    8   8    8

echo.
echo === all four done. Check each report for: ===
echo   Confidence Level = High
echo   Design Nets Matched ^>= ~70%%
echo   xsim.log contains "PASS: all lanes bit-exact"
echo.
echo Reports: results\syn\*_power_saif.rpt
