@echo off
REM =====================================================================
REM  saif_power.bat -- measured-activity power, end to end.
REM
REM  NOTE: every Vivado tool below is invoked with `call`. vivado/xvlog/
REM  xelab/xsim are .bat wrappers on Windows; without `call`, cmd transfers
REM  control to them and NEVER RETURNS, so the script silently stops after
REM  the first Vivado step and the vector restore never runs.
REM
REM  Run from the repo root, AFTER syn/run_ooc.tcl has produced the
REM  routed checkpoints, and with Vivado on the PATH:
REM      C:\Xilinx\Vivado\2024.1\settings64.bat
REM      cd "C:\College\Senorita ADMM\admm"
REM      syn\saif_power.bat main9_uniform 9 0
REM      syn\saif_power.bat uniform18     16 0
REM
REM  args:  %1 = build tag   %2 = F_MAIN of that build   %3 = ASYMMETRIC
REM
REM  *** READ THIS FIRST ***
REM  Vectors must exist at the SAME F_MAIN as the build. For anything other
REM  than F_MAIN=16 you must regenerate them:
REM        python model\gen_vectors_fm.py 9
REM  That OVERWRITES tb\vectors\*_unif.mem, and the committed set is F=16,
REM  which the iverilog regression depends on. This script backs them up to
REM  tb\vectors\_backup16\ and restores them at the end.
REM =====================================================================
setlocal
set TAG=%1
set FM=%2
set ASYM=%3
set FL1=%4
set FBOX=%5
set FL2=%6
if "%TAG%"=="" ( echo usage: saif_power.bat ^<tag^> ^<F_MAIN^> ^<ASYM^> [^<F_L1^> ^<F_BOX^> ^<F_L2^>] & exit /b 1 )
if "%FM%"==""  set FM=16
if "%ASYM%"=="" set ASYM=0
REM Lane widths are OPTIONAL. Give them for any build whose lanes are not all
REM equal to F_MAIN -- run_ooc.tcl's F_L1_P/F_BOX_P/F_L2_P generics OVERRIDE
REM the ASYMMETRIC preset, so the committed _asym vectors (lanes 16/8/7) are
REM WRONG for asym_derived (8/7/8) and main9_asym (9/8/9) and would fail them
REM for the wrong reason.
set VTAG=unif
if not "%ASYM%"=="0" set VTAG=asym

set OUT=results\syn
set SIMDIR=%OUT%\gl_%TAG%
if not exist "%SIMDIR%" mkdir "%SIMDIR%"
REM Vivado tools Tcl-parse their path arguments, so backslashes get eaten
REM (syn\saif_log.tcl -> synsaif_log.tcl). cmd builtins need backslashes,
REM tool arguments need forward slashes. Keep both.
set OUTF=%OUT:\=/%
set SIMDIRF=%SIMDIR:\=/%

echo.
echo === [0/4] backing up F=16 vectors ===
if not exist tb\vectors\_backup16 (
  mkdir tb\vectors\_backup16
  copy /y tb\vectors\*.mem tb\vectors\_backup16\ >nul
  echo   backed up to tb\vectors\_backup16\
) else (
  echo   backup already exists, leaving it alone
)

if not "%FL1%"=="" (
  echo === regenerating vectors: F_MAIN=%FM% lanes %FL1%/%FBOX%/%FL2% tag _%VTAG% ===
  python model\gen_vectors_cfg.py %FM% %FL1% %FBOX% %FL2% %VTAG%
  if errorlevel 1 ( echo VECTOR GEN FAILED & goto :restore )
) else (
  if not "%FM%"=="16" (
    echo === regenerating uniform vectors at F_MAIN=%FM% ===
    python model\gen_vectors_fm.py %FM%
    if errorlevel 1 ( echo VECTOR GEN FAILED & goto :restore )
  )
)

echo.
echo === [1/4] exporting post-route functional netlist ===
call vivado -mode batch -source syn/saif_power.tcl -tclargs netlist %TAG%
if not exist "%OUT%\%TAG%_funcsim.v" ( echo NETLIST EXPORT FAILED & goto :restore )

echo.
echo === [2/4] compiling gate-level simulation ===
REM Each build gets its OWN work library. Both funcsim netlists define
REM module admm_top and an identically-named set of leaf cells; compiled
REM into a shared "work" they collide, and the second elaboration can bind
REM an empty or wrong DUT -- which shows up as "0 objects" at log_saif.
set WLIB=w_%TAG%
if exist "%WLIB%" rmdir /s /q "%WLIB%"
if exist "xsim.dir\gl_%TAG%" rmdir /s /q "xsim.dir\gl_%TAG%"
REM Quote the -d arguments: cmd splits an unquoted FM=16 at the '=' and
REM xvlog then sees "16" as a filename ("Can not find file: 16").
call xvlog -d "FM=%FM%" -d "ASYM=%ASYM%" "%OUTF%/%TAG%_funcsim.v" tb/tb_admm_top_gl.v -work %WLIB% -log "%SIMDIRF%/xvlog.log"
if errorlevel 1 ( echo XVLOG FAILED & goto :restore )

REM glbl.v ships with Vivado but is not pre-compiled into work.
call xvlog "%XILINX_VIVADO%\data\verilog\src\glbl.v" -work %WLIB% -log "%SIMDIRF%/xvlog_glbl.log"
if errorlevel 1 ( echo GLBL COMPILE FAILED -- is XILINX_VIVADO set? & goto :restore )

REM glbl drives GSR; without it every flop stays at X through the whole run.
REM -debug typical is REQUIRED: log_saif needs trace information, and a
REM snapshot built without it fails with "compiled without trace information".
REM NO -generic_top: it escapes the top-level name and corrupts the SAIF.
REM Configuration is passed as -d macros on the xvlog line above instead.
call xelab -debug typical ^
      %WLIB%.tb_admm_top_gl %WLIB%.glbl -s gl_%TAG% ^
      -L unisims_ver -L simprims_ver -L unimacro_ver -L secureip ^
      -log "%SIMDIRF%/xelab.log"
if errorlevel 1 ( echo XELAB FAILED -- check %SIMDIR%\xelab.log & goto :restore )

echo.
echo === [3/4] simulating and logging SAIF ===
set SAIF_OUT=%CD:\=/%/%OUTF%/%TAG%.saif
call xsim gl_%TAG% -tclbatch syn/saif_log.tcl -log "%SIMDIRF%/xsim.log"
if not exist "%OUT%\%TAG%.saif" ( echo SAIF NOT WRITTEN & goto :restore )

REM An empty SAIF still lets report_power run -- it silently falls back to
REM VECTORLESS and emits a plausible-looking report with 0%% nets matched.
REM That number must never reach the manuscript, so stop here instead.
REM
REM Test the SAIF FILE SIZE, not the log text: xsim echoes every line of the
REM Tcl script it sources, so findstr on an error string matches the script's
REM own source code and trips even on a successful run.
set SZ=0
for %%A in ("%OUT%\%TAG%.saif") do set SZ=%%~zA
echo   SAIF size: %SZ% bytes
if %SZ% LSS 50000 (
  echo.
  echo *** SAIF IS TOO SMALL ^(%SZ% bytes^) -- NOT running report_power. ***
  echo *** Any existing %TAG%_power_saif.rpt is VECTORLESS. Delete it. ***
  goto :restore
)
findstr /c:"PASS: all lanes bit-exact" "%SIMDIR%\xsim.log" >nul
if errorlevel 1 (
  echo.
  echo *** GATE-LEVEL SIM DID NOT PASS -- activity is from a broken run. ***
  goto :restore
)

echo.
echo === [4/4] report_power with measured activity ===
call vivado -mode batch -source syn/saif_power.tcl -tclargs power %TAG%

echo.
echo Reports:  %OUT%\%TAG%_power_saif.rpt
echo Sim log:  %SIMDIR%\xsim.log   ^(contains the PASS line and cycle counts^)
echo.
echo Send back BOTH: the power report AND the THROUGHPUT lines from xsim.log.

:restore
echo.
echo === restoring F=16 vectors ===
if exist tb\vectors\_backup16\*.mem copy /y tb\vectors\_backup16\*.mem tb\vectors\ >nul
echo   done. Confirm with:  build.bat 0
endlocal
