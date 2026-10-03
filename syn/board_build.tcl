# =============================================================================
# board_build.tcl -- scripted Basys3 bitstream, with an in-context timing gate.
#
#   vivado -mode batch -source syn/board_build.tcl -tclargs <tag> <F_MAIN> <rom> <MHz> [<MHz> ...]
#
#   rom    unif   three operator sets  (python tools/make_rom.py)
#          lasso  three LASSO instances, lane forced to L1  (make_rom.py --lasso)
#   MHz    one MMCM at exactly that frequency, for EVERY build including 50.
#          Candidates are tried in the order given; the FIRST one that meets
#          setup AND hold after routing, in context, gets a bitstream. A
#          candidate that misses is reported and never written.
#
# WHY NO DIVIDER BUILD. The bring-up wrapper's default clock is a fabric /2
# divider behind a LUT mux (sw[3] selects raw 100 MHz). Run through this gate
# on 2026-10-03 it failed at "50 MHz" with WNS -5.69 / WHS -2.59 ns: the mux
# puts BOTH clk100 and the divided clock on the design clock net, so Vivado
# times the core at 100 MHz and across the two clocks, and the LUT-routed
# clock has the skew to produce thousands of hold violations. The session-1
# GUI bitstreams had the same structure; the GUI writes a bitstream anyway.
# One MMCM on a BUFG gives one clean clock domain at any frequency.
#
# Examples (from the repo root, F=9 vectors already generated):
#   ... -tclargs main9 9 lasso 50            (-> main9_lasso_mmcm50.bit)
#   ... -tclargs main9 9 unif 85 82.5 80 77.5 75
#   ... -tclargs uniform18 16 unif 66.25 65 62.5 60
#
# Outputs:
#   results/board/<tag>_<rom>_<clk>.bit                     (git-ignored)
#   results/syn/board_<tag>_<rom>_<clk>_{timing,util}.rpt   (committed evidence)
#
# WHY THE GUARDS. Two board failures in this project read as a PASS: a ROM that
# failed to load (0 == 0), and a ROM at the wrong F_MAIN. This script refuses
# to build if the ROM width does not match F_MAIN or the ROM is not the exact
# concatenation of the golden vectors it claims to hold.
# =============================================================================

if {[llength $argv] < 4} {
    error "usage: -tclargs <tag> <F_MAIN> <unif|lasso> <MHz> \[<MHz> ...\]"
}
set TAG   [lindex $argv 0]
set FM    [lindex $argv 1]
set ROM   [lindex $argv 2]
set MHZS  [lrange $argv 3 end]
set PART  xc7a35tcpg236-1

set HERE  [file normalize [file dirname [info script]]]
set ROOT  [file normalize $HERE/..]
set RTL   $ROOT/rtl
set VEC   $ROOT/tb/vectors
set BOARD $ROOT/results/board
set REP   $ROOT/results/syn
file mkdir $BOARD $REP

proc slurp {p} {
    set fh [open $p r]; set d [read $fh]; close $fh
    set out {}
    foreach l [split $d "\n"] { set l [string trim $l]; if {$l ne ""} { lappend out $l } }
    return $out
}

# ---- guard 1: ROM is the exact concatenation of the golden vectors --------
if {$ROM eq "unif"} {
    set parts {l1_unif box_unif l2_unif}
} elseif {$ROM eq "lasso"} {
    set parts {l1_lasso0 l1_lasso1 l1_lasso2}
} else { error "rom must be unif or lasso, got '$ROM'" }
foreach k {M q z} {
    set want {}
    foreach p $parts { set want [concat $want [slurp $VEC/${k}_${p}.mem]] }
    if {[slurp $VEC/${k}_all.mem] ne $want} {
        error "tb/vectors/${k}_all.mem is not ${parts}. Run: python tools/make_rom.py[expr {$ROM eq "lasso" ? " --lasso" : ""}]"
    }
}
# ---- guard 2: ROM word width matches F_MAIN --------------------------------
set digits [expr {int(ceil((2.0 + $FM) / 4.0))}]
set w0 [string length [lindex [slurp $VEC/z_all.mem] 0]]
if {$w0 != $digits} {
    error "ROM words are $w0 hex digits, F_MAIN=$FM needs $digits. Regenerate the vectors at F_MAIN=$FM."
}
puts "ROM ok: $ROM, $digits hex digits per word (F_MAIN=$FM)"

set SRC [list $RTL/basys3_wrapper.v $RTL/uart_tx.v $RTL/q_cast.v $RTL/sat_shift.v \
              $RTL/max_tree.v $RTL/pe_mac.v $RTL/systolic_array.v \
              $RTL/reconfigurable_prox.v $RTL/admm_top.v]

# Exact MMCM settings for f MHz: f = 100 * M / D, M and D on the 0.125 grid,
# VCO = 100 * M within 600-1200 MHz (-1 speed grade).
proc mmcm_for {f} {
    for {set d 2} {$d <= 64} {incr d} {
        set m [expr {$f * $d / 100.0}]
        if {abs($m * 8 - round($m * 8)) > 1e-6} { continue }
        set vco [expr {100.0 * $m}]
        if {$vco >= 600.0 && $vco <= 1200.0 && $m >= 2.0 && $m <= 64.0} {
            return [list [format %.3f $m] [format %.3f $d]]
        }
    }
    error "no exact MMCM setting for $f MHz; pick a multiple of 0.125*100/D"
}

proc slack {kind} {
    set p [get_timing_paths -quiet -max_paths 1 -nworst 1 -$kind]
    if {$p eq ""} { return "n/a" }
    return [get_property SLACK [lindex $p 0]]
}

set results {}
set built ""
foreach mhz $MHZS {
    set clk  mmcm[string map {. p} $mhz]
    set name ${TAG}_${ROM}_${clk}
    set defs [list F_MAIN=$FM]
    if {$ROM eq "lasso"} { lappend defs LASSO_ROM=1 }

    # constraints: drop the divider's generated clock (the divider does not
    # exist in an MMCM build); Vivado derives the MMCM output clock itself.
    set xdc_in [slurp $HERE/basys3.xdc]
    set xdc $BOARD/run_${name}.xdc
    set fh [open $xdc w]
    set skip 0
    foreach l $xdc_in {
        if {$skip} { set skip [string match {*\\} $l]; continue }
        if {[string match {create_generated_clock*} $l]} {
            set skip [string match {*\\} $l]; continue
        }
        puts $fh $l
    }
    close $fh
    lassign [mmcm_for $mhz] M D
    lappend defs MMCM_MULT=$M MMCM_DIV=$D CLK_HZ=[expr {int(round($mhz * 1e6))}]
    puts "\n=========== $name : MMCM M=$M D=$D -> [expr {100.0*$M/$D}] MHz ==========="

    # $readmemh resolves relative to the run directory: give it its own copy.
    set run $BOARD/run_${name}
    file mkdir $run
    foreach k {M q z} { file copy -force $VEC/${k}_all.mem $run/${k}_all.mem }
    set here [pwd]
    cd $run

    create_project -in_memory -part $PART
    foreach f $SRC { read_verilog $f }
    add_files -norecurse [glob $run/*_all.mem]
    set_property include_dirs $RTL [current_fileset]
    read_xdc $xdc
    synth_design -top basys3_wrapper -part $PART -include_dirs $RTL -verilog_define $defs
    opt_design
    place_design
    phys_opt_design
    route_design

    set wns [slack setup]
    set whs [slack hold]
    report_timing_summary -file $REP/board_${name}_timing.rpt
    report_utilization    -file $REP/board_${name}_util.rpt
    set met [expr {$wns ne "n/a" && $whs ne "n/a" && $wns >= 0 && $whs >= 0}]
    puts "BOARD $name : WNS=$wns WHS=$whs [expr {$met ? "MET" : "MISS"}]"
    lappend results "$name  WNS=$wns  WHS=$whs  [expr {$met ? "MET" : "MISS"}]"
    if {$met} {
        write_bitstream -force $BOARD/${name}.bit
        set built $BOARD/${name}.bit
    }
    close_project
    cd $here
    if {$met} { break }
}

puts "\n================ SUMMARY ================"
foreach r $results { puts $r }
if {$built eq ""} {
    puts "NO BITSTREAM: no candidate met timing in context."
} else {
    puts "bitstream: $built"
}
