# =============================================================================
# saif_power.tcl -- vector-based power from real switching activity.
#
# Replaces every vectorless report_power estimate in STATUS.md, including the
# 78 mW headline. Vectorless power assumes a default toggle rate on every net;
# for a datapath that idles between iterations that assumption is not defensible
# and a reviewer will ask.
#
# TWO STAGES. This file is both.
#
#   stage 1 (netlist):  vivado -mode batch -source syn/saif_power.tcl -tclargs netlist <tag>
#   stage 2 (power):    vivado -mode batch -source syn/saif_power.tcl -tclargs power   <tag>
#
# Between them, run the gate-level simulation that writes the SAIF -- see
# syn/saif_power.bat, which drives all three steps in order.
#
# <tag> is one of the run_ooc.tcl build tags. The one that matters is
# main9_uniform (the design point); uniform18 gives the baseline to quote the
# reduction against.
# =============================================================================

set MODE [lindex $argv 0]
set TAG  [lindex $argv 1]
if {$MODE eq "" || $TAG eq ""} {
    puts "usage: -tclargs <netlist|power> <tag>"
    return
}

set HERE   [file normalize [file dirname [info script]]]
set ROOT   [file normalize $HERE/..]
set OUTDIR $ROOT/results/syn
set DCP    $OUTDIR/${TAG}_routed.dcp

if {![file exists $DCP]} {
    puts "ERROR: no checkpoint at $DCP -- run syn/run_ooc.tcl first."
    return
}

if {$MODE eq "netlist"} {
    # ---- stage 1: functional netlist for simulation -------------------------
    # funcsim, not timesim: a timing netlist needs SDF annotation and will
    # propagate X through the reset if GSR is not modelled exactly. Switching
    # activity from funcsim is what report_power actually consumes; the SDF
    # only changes glitch counts. Start here, and only move to timesim if the
    # reviewer asks for glitch power.
    open_checkpoint $DCP
    write_verilog -mode funcsim -force $OUTDIR/${TAG}_funcsim.v
    puts "wrote $OUTDIR/${TAG}_funcsim.v"
    close_project

} elseif {$MODE eq "power"} {
    # ---- stage 2: power with measured activity ------------------------------
    set SAIF $OUTDIR/${TAG}.saif
    if {![file exists $SAIF]} {
        puts "ERROR: no SAIF at $SAIF -- run the gate-level sim first."
        return
    }
    open_checkpoint $DCP
    read_saif -strip_path tb_admm_top_gl/dut $SAIF

    report_power -file $OUTDIR/${TAG}_power_saif.rpt
    report_power -advisory -file $OUTDIR/${TAG}_power_saif_advisory.rpt

    set ps [report_power -return_string]
    foreach l [split $ps "\n"] {
        if {[string match "*Dynamic (W)*" $l] ||
            [string match "*Device Static (W)*" $l] ||
            [string match "*Total On-Chip Power*" $l] ||
            [string match "*Confidence*" $l]} {
            puts [string trim $l]
        }
    }
    puts ""
    puts "CHECK THE CONFIDENCE LEVEL in ${TAG}_power_saif.rpt."
    puts "It must read High. Medium or Low means the SAIF did not annotate --"
    puts "usually a -strip_path mismatch, in which case the number is still"
    puts "vectorless and must NOT be reported as measured."
    close_project

} else {
    puts "unknown mode '$MODE' -- expected netlist or power"
}
