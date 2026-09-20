# =============================================================================
# critpath.tcl -- WHERE does the critical path live, per build?
#
#     vivado -mode batch -source syn/critpath.tcl > results/syn/critpath.log 2>&1
#
# WHY. Fmax across the seven builds does not follow a single story:
#
#   lanes == F_MAIN : 66.3 (F16)  79.7 (F10)  85.4 (F9)   <- monotone
#   lanes <  F_MAIN : 67.6 (F16)  68.9 (F10)  86.5 (F9)   <- not monotone
#
# main10_lane8 (F_MAIN=10, lanes 8) lands at 68.9 where its lane-uniform
# sibling reaches 79.7, while uniform10 (F_MAIN=16, lanes 8) is FASTER than
# its lane-uniform sibling. Guessing has failed twice; this measures it.
#
# HYPOTHESIS H: Fmax = min(main-datapath path, lane path), and which binds
# changes with F_MAIN. At F_MAIN=16 the main datapath is slow enough to bind
# regardless of lanes; at F_MAIN=10 it is fast enough that a narrowed lane
# path binds instead.
#
# PREDICTIONS (each can fail):
#   P1  lane-uniform builds  -> worst path in u_array / accumulator / FSM
#   P2  main10_lane8         -> worst path in a prox lane or its q_narrow cast
#   P3  main9_asym           -> worst path NOT in the narrowed Box lane
#                               (it shows no Fmax penalty, so if the lane path
#                               bound there we would see one)
# If P1 and P2 both land in the same module, H is refuted.
#
# Each build is implemented at ITS OWN measured Fmax period, because the
# worst path at a relaxed 20 ns constraint need not be the one that binds at
# Fmax. ~7 implementations, ~45 min unattended.
# =============================================================================

set PART   xc7a35tcpg236-1
set HERE   [file normalize [file dirname [info script]]]
set ROOT   [file normalize $HERE/..]
set RTL    $ROOT/rtl
set OUTDIR $ROOT/results/syn
file mkdir $OUTDIR

set SRC [list \
    $RTL/q_cast.v $RTL/sat_shift.v $RTL/max_tree.v $RTL/pe_mac.v \
    $RTL/systolic_array.v $RTL/reconfigurable_prox.v $RTL/admm_top.v]

#          tag            ASYM DSP  N  F_L1 F_BOX F_L2 F_MAIN  period(ns)
set BUILDS {
    uniform18              0   0   8  16   16    16   16      15.079
    uniform10              0   0   8   8    8     8   16      14.797
    asym_derived           1   0   8   8    7     8   16      15.640
    main10_uniform         0   0   8  10   10    10   10      12.547
    main10_lane8           0   0   8   8    8     8   10      14.516
    main9_uniform          0   0   8   9    9     9    9      11.703
    main9_asym             1   0   8   9    8     9    9      11.562
}

set summary {}
foreach {tag asym dsp n fl1 fbox fl2 fm per} $BUILDS {
    puts "\n================ $tag  @ $per ns ================"
    create_project -in_memory -part $PART
    set_property source_mgmt_mode None [current_project]
    foreach f $SRC { read_verilog $f }
    set_property include_dirs $RTL [current_fileset]

    set xdc $OUTDIR/critpath_${tag}.xdc
    set fh [open $xdc w]
    puts $fh "create_clock -period $per -name clk \[get_ports clk\]"
    puts $fh "set_input_delay  -clock clk 1.0 \[get_ports -filter {DIRECTION == IN  && NAME != \"clk\"}\]"
    puts $fh "set_output_delay -clock clk 1.0 \[get_ports -filter {DIRECTION == OUT}\]"
    close $fh
    read_xdc -mode out_of_context $xdc

    synth_design -top admm_top -mode out_of_context \
        -generic ASYMMETRIC=$asym -generic USE_DSP_L2=$dsp -generic N=$n \
        -generic F_L1_P=$fl1 -generic F_BOX_P=$fbox -generic F_L2_P=$fl2 \
        -verilog_define F_MAIN=$fm -flatten_hierarchy none
    opt_design
    place_design
    phys_opt_design
    route_design

    # Full detail on the ten worst setup paths.
    report_timing -setup -max_paths 10 -nworst 10 -path_type full_clock_expanded \
        -input_pins -file $OUTDIR/${tag}_critpath.rpt

    # Condensed: where does the worst path start and end?
    set p [get_timing_paths -quiet -max_paths 1 -setup]
    set src "n/a" ; set dst "n/a" ; set wns "n/a" ; set lvl "n/a"
    if {$p ne ""} {
        set p0  [lindex $p 0]
        set wns [get_property SLACK $p0]
        set lvl [get_property LOGIC_LEVELS $p0]
        # STARTPOINT_PIN / ENDPOINT_PIN are not valid properties on timing
        # path objects in Vivado 2025.2 -- they return null. Use the cell
        # properties, which do exist, and fall back to parsing the report.
        foreach prop {STARTPOINT_PIN STARTPOINT} {
            catch {set v [get_property $prop $p0]}
            if {[info exists v] && $v ne "" && $v ne "null"} { set src $v ; break }
        }
        foreach prop {ENDPOINT_PIN ENDPOINT} {
            catch {set w [get_property $prop $p0]}
            if {[info exists w] && $w ne "" && $w ne "null"} { set dst $w ; break }
        }
        # Definitive fallback: the per-build report always has the endpoints.
        if {$src eq "n/a"} { set src "see ${tag}_critpath.rpt (Source:)" }
        if {$dst eq "n/a"} { set dst "see ${tag}_critpath.rpt (Destination:)" }
    }
    puts "WORST PATH  slack=$wns  levels=$lvl"
    puts "  from: $src"
    puts "  to  : $dst"
    lappend summary [list $tag $wns $lvl $src $dst]
    close_project
}

puts "\n==================== CRITICAL PATH SUMMARY ===================="
foreach s $summary {
    lassign $s tag wns lvl src dst
    puts [format "%-16s slack=%-8s levels=%-4s" $tag $wns $lvl]
    puts "    from $src"
    puts "    to   $dst"
}
puts "==============================================================="
puts ""
puts "Read the module names in the start/end pins:"
puts "  u_array / systolic  -> main datapath"
puts "  G_PROX\[i\].u_prox    -> proximal lane"
puts "  q_narrow / q_cast   -> narrowing cast (the suspected culprit)"
puts "If lane-uniform and lane-narrowed builds bind in the SAME module,"
puts "hypothesis H is refuted and the Fmax spread is not a path-location"
puts "effect."
