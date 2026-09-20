# =============================================================================
# fmax_sweep.tcl -- find the real Fmax ceiling per build.
#
#     C:\Xilinx\Vivado\2024.1\settings64.bat
#     cd "C:\College\Senorita ADMM\admm"
#     vivado -mode batch -source syn/fmax_sweep.tcl
#
# WHY: run_ooc.tcl targets 20 ns (50 MHz), chosen defensively after an 8 ns
# attempt missed by 19 ns. Everything then met timing with slack to spare, so
# the reported 71.1 MHz is "20 ns minus whatever slack fell out", not a
# ceiling. Quoting it as Fmax is not defensible, and the +20.7% Fmax headline
# is a ratio of two such numbers.
#
# METHOD: binary search on the constraint per build. A build "passes" at a
# period if post-route WNS >= 0. The reported Fmax is 1000/period of the
# tightest passing period -- a constraint the design actually met, not an
# extrapolation from slack.
#
# COST: STEPS full implementations per tag. At ~6 min each that is roughly
# 40 min per tag, 80 min for both. Unattended.
# =============================================================================

set PART   xc7a35tcpg236-1
set STEPS  7                 ;# binary search resolution
set LO     2.0               ;# ns, optimistic bound
set HI     20.0              ;# ns, known-good bound

set HERE   [file normalize [file dirname [info script]]]
set ROOT   [file normalize $HERE/..]
set RTL    $ROOT/rtl
set OUTDIR $ROOT/results/syn
file mkdir $OUTDIR

set SRC [list \
    $RTL/q_cast.v $RTL/sat_shift.v $RTL/max_tree.v $RTL/pe_mac.v \
    $RTL/systolic_array.v $RTL/reconfigurable_prox.v $RTL/admm_top.v]

# The two builds the headline compares. Same source, differing generics --
# any other comparison is not defensible.
#         tag           ASYM DSP N  F_L1 F_BOX F_L2 F_MAIN
set BUILDS {
    uniform18            0   0   8  16   16    16   16
    main9_uniform        0   0   8   9    9     9    9
}

# The remaining four, which still carry Fmax extrapolated from a 20 ns
# constraint. Uncomment to sweep them; adds ~40 min per build.
set BUILDS_REST {
    uniform10            0   0   8   8    8     8   16
    asym_derived         1   0   8   8    7     8   16
    main10_uniform       0   0   8  10   10    10   10
    main9_asym           1   0   8   9    8     9    9
    main10_lane8         0   0   8   8    8     8   10
}
if {[info exists ::env(SWEEP_ALL)]} {
    set BUILDS [concat $BUILDS $BUILDS_REST]
    puts "SWEEP_ALL set -- sweeping all six builds (~4 h)"
}

proc impl_at {period tag asym dsp n fl1 fbox fl2 fmain} {
    global PART SRC RTL OUTDIR
    create_project -in_memory -part $PART
    set_property source_mgmt_mode None [current_project]
    foreach f $SRC { read_verilog $f }
    set_property include_dirs $RTL [current_fileset]

    # Constraints written per period -- the whole point is that synthesis is
    # timing-driven, so the constraint must be in place BEFORE synth_design.
    set xdc $OUTDIR/sweep_${tag}.xdc
    set fh [open $xdc w]
    puts $fh "create_clock -period $period -name clk \[get_ports clk\]"
    puts $fh "set_input_delay  -clock clk 1.0 \[get_ports -filter {DIRECTION == IN  && NAME != \"clk\"}\]"
    puts $fh "set_output_delay -clock clk 1.0 \[get_ports -filter {DIRECTION == OUT}\]"
    close $fh
    read_xdc -mode out_of_context $xdc

    synth_design -top admm_top -mode out_of_context \
        -generic ASYMMETRIC=$asym -generic USE_DSP_L2=$dsp -generic N=$n \
        -generic F_L1_P=$fl1 -generic F_BOX_P=$fbox -generic F_L2_P=$fl2 \
        -verilog_define F_MAIN=$fmain \
        -flatten_hierarchy none
    opt_design
    place_design
    phys_opt_design
    route_design

    set wns "n/a"
    set p [get_timing_paths -quiet -max_paths 1 -setup]
    if {$p ne ""} { set wns [get_property SLACK [lindex $p 0]] }

    # A build that meets setup but drops LUTs is a build that got
    # constant-folded. Catch it here rather than in the results table.
    set luts [llength [get_cells -hier -quiet -filter "REF_NAME =~ LUT*"]]
    close_project
    return [list $wns $luts]
}

set summary {}
foreach {tag asym dsp n fl1 fbox fl2 fm} $BUILDS {
    puts "\n================ sweeping $tag ================"
    set lo $LO
    set hi $HI
    set best "none"
    set best_luts 0

    for {set i 0} {$i < $STEPS} {incr i} {
        set mid [format "%.3f" [expr {($lo + $hi) / 2.0}]]
        puts "\n--- $tag : trying period $mid ns ([expr {1000.0/$mid}] MHz) ---"
        set r [impl_at $mid $tag $asym $dsp $n $fl1 $fbox $fl2 $fm]
        set wns  [lindex $r 0]
        set luts [lindex $r 1]

        if {$wns ne "n/a" && $wns >= 0} {
            puts "    MET   WNS=$wns  LUT=$luts"
            set best $mid
            set best_luts $luts
            set hi $mid
        } else {
            puts "    MISS  WNS=$wns  LUT=$luts"
            set lo $mid
        }
    }

    if {$best eq "none"} {
        lappend summary [list $tag "n/a" "n/a" "n/a"]
    } else {
        lappend summary [list $tag $best [format "%.1f" [expr {1000.0/$best}]] $best_luts]
    }
}

puts ""
puts "======================== FMAX SUMMARY ========================"
puts [format "%-16s %12s %12s %8s" tag "period(ns)" "Fmax(MHz)" LUT]
foreach s $summary {
    puts [format "%-16s %12s %12s %8s" {*}$s]
}
puts "============================================================="
puts ""
puts "Report the tightest period that MET, not 1000/(period-slack)."
puts "If LUT counts differ wildly between the two tags at their own Fmax,"
puts "the area and speed numbers come from different design points and the"
puts "-46.6%/+20.7% pair cannot be quoted together without saying so."
