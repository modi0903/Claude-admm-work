@echo off
REM =====================================================================
REM  build.bat  --  run from the folder that contains rtl\ tb\ model\ syn\
REM  Usage:   build.bat        (asymmetric)
REM           build.bat 0      (uniform baseline)
REM =====================================================================
setlocal
set ASYM=%1
if "%ASYM%"=="" set ASYM=1

echo.
echo === Compiling ADMM accelerator, ASYMMETRIC=%ASYM% ===
iverilog -g2005 -Irtl -o sim%ASYM%.vvp -Ptb_admm_top.ASYMMETRIC=%ASYM% ^
  tb\tb_admm_top.v ^
  rtl\q_cast.v ^
  rtl\max_tree.v ^
  rtl\sat_shift.v ^
  rtl\pe_mac.v ^
  rtl\systolic_array.v ^
  rtl\reconfigurable_prox.v ^
  rtl\admm_top.v

if errorlevel 1 (
  echo COMPILE FAILED
  exit /b 1
)

echo === Running ===
vvp sim%ASYM%.vvp
endlocal
