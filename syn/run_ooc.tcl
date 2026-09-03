# =============================================================================
# run_ooc.tcl -- OOC synthesis + implementation, Artix-7 xc7a35tcpg236-1
#
# From the Vivado Tcl Console:
#     cd {C:/College/Senorita ADMM/admm_project}
#     source syn/run_ooc.tcl
#
# Baseline and asymmetric build from THE SAME SOURCE FILES, differing by one
# generic (ASYMMETRIC). Same constraints, same strategy. Any other comparison
# methodology is not defensible and a TCAS-II reviewer will say so.
#
# Written against the common subset of the Vivado Tcl API -- no
# remove_from_collection, no collection arithmetic, no version-specific
# properties.
# =============================================================================

set PART   xc7a35tcpg236-1
set PERIOD 20.000   ;# 50 MHz. The previous 8 ns target failed by 19 ns;
                    ;# meet timing first, then close the gap deliberately.

set HERE   [file normalize [file dirname [info script]]]
set ROOT   [file normalize $HERE/..]
set RTL    $ROOT/rtl
set OUTDIR $ROOT/results/syn
file mkdir $OUTDIR

set SRC [list \
    $RTL/q_cast.v $RTL/sat_shift.v $RTL/max_tree.v $RTL/pe_mac.v \
    $RTL/systolic_array.v $RTL/reconfigurable_prox.v $RTL/admm_top.v]

# ---- constraints, written once and read before synthesis so timing-driven ----
set XDC $OUTDIR/ooc.xdc
set fh [open $XDC w]
puts $fh "create_clock -period $PERIOD -name clk \[get_ports clk\]"
puts $fh "set_input_delay  -clock clk 1.0 \[get_ports -filter {DIRECTION == IN  && NAME != \"clk\"}\]"
puts $fh "set_output_delay -clock clk 1.0 \[get_ports -filter {DIRECTION == OUT}\]"
close $fh

proc count_ref {pat} {
    set c [get_cells -hier -quiet -filter "REF_NAME =~ $pat"]
    if {$c eq ""} { return 0 }
    return [llength $c]
}

proc worst_slack {} {
    set p [get_timing_paths -quiet -max_paths 1 -delay_type max_min]
    if {$p eq ""} { return "n/a" }
    return [get_property SLACK [lindex $p 0]]
}

proc build {tag asym dsp n {fl1 -1} {fbox -1} {fl2 -1} {fmain 16}} {
    global PART SRC RTL XDC OUTDIR

    create_project -in_memory -part $PART
    set_property source_mgmt_mode None [current_project]
    foreach f $SRC { read_verilog $f }
    set_property include_dirs $RTL [current_fileset]
    read_xdc -mode out_of_context $XDC

    # OOC: no I/O buffers, so the report is pure core logic.
    # prox_mode MUST stay a live port -- if it is constant-folded, two of the
    # three proximal lanes are deleted and the area saving is fictional.
    synth_design -top admm_top -mode out_of_context \
        -generic ASYMMETRIC=$asym -generic USE_DSP_L2=$dsp -generic N=$n \
        -generic F_L1_P=$fl1 -generic F_BOX_P=$fbox -generic F_L2_P=$fl2 \
        -verilog_define F_MAIN=$fmain \
        -flatten_hierarchy none

    opt_design
    report_utilization -hierarchical -file $OUTDIR/${tag}_util_synth.rpt
    report_timing_summary -file $OUTDIR/${tag}_timing_synth.rpt

    place_design
    phys_opt_design
    route_design

    report_utilization -hierarchical -file $OUTDIR/${tag}_util_route.rpt
    report_timing_summary -file $OUTDIR/${tag}_timing_route.rpt
    report_power          -file $OUTDIR/${tag}_power_route.rpt
    write_checkpoint -force $OUTDIR/${tag}_routed.dcp

    set luts [count_ref "LUT*"]
    set ffs  [count_ref "FD*"]
    set dsps [count_ref "DSP48*"]
    set crys [count_ref "CARRY*"]
    puts ""
    puts "RESULT $tag : LUT=$luts  FF=$ffs  DSP=$dsps  CARRY=$crys  WNS=[worst_slack]"
    puts ""
    close_project
}

# The main-datapath sweep showed F_M dominates the error budget: at NMSE 1e-4
# every operator needs F_M=9 whether the lanes are pinned at 8/7/8 or tied to
# F_M. Narrow lanes buy no accuracy and (per the previous sweep) cost LUTs, so
# the design point is FULLY UNIFORM at the derived width.
#
#            tag          ASYM DSP  F_L1 F_BOX F_L2  F_MAIN
foreach {tag asym dsp fl1 fbox fl2 fm} {
    uniform18             0   0    16   16    16     16
    uniform10             0   0     8    8     8     16
    asym_derived          1   0     8    7     8     16
    main10_uniform        0   0    10   10    10     10
    main9_uniform         0   0     9    9     9      9
    main9_asym            1   0     9    8     9      9
} {
    puts "
=========== $tag  (lanes $fl1/$fbox/$fl2, F_MAIN=$fm) ==========="
    build $tag $asym $dsp 8 $fl1 $fbox $fl2 $fm
}

puts "reports written to $OUTDIR"
puts ""
puts "In the *_util_route.rpt hierarchical table, the rows that matter:"
puts "  u_array/            systolic engine   (must be IDENTICAL in both)"
puts "  G_PROX\[*\].u_prox    the three proximal lanes  (this is the saving)"
puts "  remainder           FSM, dual update, residual reduction"
puts ""
puts "SANITY CHECK: DSP must be 64 in both builds. If the asymmetric build"
puts "has fewer proximal-lane cells than expected, check that all three lanes"
puts "still exist -- a lane that got constant-folded away is a fake saving."
