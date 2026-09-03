# =============================================================================
# harvest.tcl -- collect every number from the four routed checkpoints into
# one table. Reopens the .dcp files, so it does not depend on report format.
#
#     cd {C:/College/Senorita ADMM/admm_project}
#     source syn/harvest.tcl
#
# Copy the whole SUMMARY block back.
# =============================================================================

set HERE   [file normalize [file dirname [info script]]]
set OUTDIR [file normalize $HERE/../results/syn]
set TAGS   {uniform18 uniform10 asym_derived main10_uniform main9_uniform main9_asym}
set PERIOD 20.000

proc nlut {pat} {
    return [llength [get_cells -hier -quiet -filter "REF_NAME =~ LUT* && NAME =~ $pat"]]
}
proc nref {pat} {
    return [llength [get_cells -hier -quiet -filter "REF_NAME =~ $pat"]]
}
proc nrefin {ref pat} {
    return [llength [get_cells -hier -quiet -filter "REF_NAME =~ $ref && NAME =~ $pat"]]
}

set rows {}
foreach tag $TAGS {
    set dcp $OUTDIR/${tag}_routed.dcp
    if {![file exists $dcp]} {
        puts "SKIP $tag  (no checkpoint at $dcp)"
        continue
    }
    puts "opening $tag ..."
    open_checkpoint $dcp

    set lut_all   [nref "LUT*"]
    set ff_all    [nref "FD*"]
    set dsp_all   [nref "DSP48*"]
    set car_all   [nref "CARRY*"]
    set lut_prox  [nlut "*G_PROX*"]
    set lut_array [nlut "*u_array*"]
    set dsp_prox  [nrefin "DSP48*" "*G_PROX*"]
    set car_prox  [nrefin "CARRY*" "*G_PROX*"]
    set lut_rest  [expr {$lut_all - $lut_prox - $lut_array}]

    set wns "n/a"
    if {![catch {set p [get_timing_paths -quiet -max_paths 1 -setup]}]} {
        if {$p ne ""} { set wns [get_property SLACK [lindex $p 0]] }
    }
    set fmax "n/a"
    if {$wns ne "n/a" && [expr {$PERIOD - $wns}] > 0} {
        set fmax [format "%.1f" [expr {1000.0 / ($PERIOD - $wns)}]]
    }

    set dynp "n/a"
    if {![catch {set ps [report_power -return_string]}]} {
        foreach l [split $ps "\n"] {
            if {[string match "*Dynamic (W)*" $l]} {
                set f [split [string map {| " "} $l]]
                foreach t $f { if {[string is double -strict $t]} { set dynp $t ; break } }
            }
        }
    }

    lappend rows [list $tag $lut_all $lut_prox $lut_array $lut_rest \
                       $ff_all $dsp_all $dsp_prox $car_all $car_prox $wns $fmax $dynp]
    close_project
}

puts ""
puts "================================ SUMMARY ================================"
puts [format "%-15s %6s %6s %6s %6s %6s %4s %5s %6s %6s %9s %8s %8s" \
      tag LUTtot LUTprx LUTarr LUTrst FF DSP DSPprx CARRY CARprx WNS Fmax DynW]
foreach r $rows {
    puts [format "%-15s %6s %6s %6s %6s %6s %4s %5s %6s %6s %9s %8s %8s" {*}$r]
}
puts "========================================================================="

# Two builds with different generics must not produce identical netlists.
# A previous run had main9_uniform and main9_asym match in all twelve columns
# because a constant-derivation bug saturated the lane constants to garbage in
# both. Identical rows are always a bug, never a result.
set seen [dict create]
set dup 0
foreach r $rows {
    set key [join [lrange $r 1 end] ","]
    if {[dict exists $seen $key]} {
        puts "  *** WARNING: [lindex $r 0] is byte-identical to [dict get $seen $key]"
        puts "      Different generics cannot give identical netlists. Check that"
        puts "      the -generic values actually reached the design."
        set dup 1
    }
    dict set seen $key [lindex $r 0]
}
if {!$dup} { puts "  sanity: all builds distinct" }
puts ""
puts "LUTprx = LUTs inside the 8 proximal lanes   <-- where the asymmetry acts"
puts "LUTarr = systolic array   (must be equal across all four builds)"
puts "LUTrst = FSM + dual update + residual tree + pre-combine"
puts ""
puts "Key comparisons:"
puts "  uniform_dsp   vs asym_dsp     what a designer actually gets on this part"
puts "  uniform_nodsp vs asym_nodsp   what the WORDLENGTH alone buys (no macro confound)"
