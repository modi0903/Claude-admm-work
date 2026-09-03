QUICK START (Windows)
=====================

Unzip so you have this structure -- do NOT flatten it:

    admm\
       build.bat
       rtl\      (7 files, including admm_defs.vh)
       tb\       tb_admm_top.v  and  tb\vectors\ (19 .mem files)
       model\    (4 python files)
       syn\      run_ooc.tcl
       STATUS.md

STEP 1 -- simulate (2 min)
--------------------------
Open cmd, then:

    cd "C:\College\Senorita ADMM\admm"
    build.bat 1
    build.bat 0

Expect for BOTH:   PASS: all lanes bit-exact vs golden model

Run build.bat from the admm folder itself. The testbench opens
tb/vectors/*.mem using a path relative to where you launch it.

If iverilog is missing, use Vivado's simulator instead -- first put it on
the PATH by running (adjust the version):

    C:\Xilinx\Vivado\2024.1\settings64.bat

then:

    xvlog -i rtl rtl\q_cast.v rtl\sat_shift.v rtl\pe_mac.v rtl\systolic_array.v rtl\reconfigurable_prox.v rtl\admm_top.v tb\tb_admm_top.v
    xelab -generic_top "ASYMMETRIC=1" tb_admm_top -s simtop
    xsim simtop -R

STEP 2 -- synthesis (20 min)  <-- the part only you can do
----------------------------------------------------------
    C:\Xilinx\Vivado\2024.1\settings64.bat
    cd "C:\College\Senorita ADMM\admm"
    vivado -mode batch -source syn/run_ooc.tcl

Reports land in results\syn\. Send back:
    baseline_uniform_util_route.rpt
    proposed_asym_util_route.rpt
    baseline_uniform_timing_route.rpt
    proposed_asym_timing_route.rpt

STEP 3
------
Nothing. Read STATUS.md whenever you're awake.

Python side (optional, needs numpy only):
    python model\gen_vectors.py       regenerate test vectors
    python model\experiments.py       wordlength / convergence / BER
    python model\sweep_ordering.py    operating-point sweep (~15 min)
