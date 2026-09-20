# xsim batch script -- log DUT switching activity to SAIF.
# Invoked by saif_power.bat as:  xsim <snap> -tclbatch syn/saif_log.tcl
#
# TWO HARD RULES, both learned the painful way:
#
# 1. NEVER log /* . That sweeps in the testbench, whose 2-D reg arrays
#    (m_mem, q_mem, z_exp) emit SAIF constructs Vivado's parser rejects
#    ("syntax error, unexpected WORD"). The resulting file cannot be read
#    at all, and read_saif then reports 1 of N nets matched.
#
# 2. Enter the scope with current_scope, then use a RELATIVE pattern.
#    get_objects with an absolute path pattern silently returns 0 in some
#    snapshots, which is how an empty SAIF gets produced without any error.

set saif [file normalize $::env(SAIF_OUT)]

# Reset first so the reset transient is not counted as workload activity.
run 200 ns

puts "SAIF: ---- scopes visible from root ----"
catch {report_scopes /} rs
puts $rs
puts "SAIF: ------------------------------------"

set objs {}
set chosen ""
foreach c [list /tb_admm_top_gl/dut tb_admm_top_gl/dut dut] {
    if {[catch {current_scope $c} err]} {
        puts "SAIF: current_scope '$c' failed: $err"
        continue
    }
    set here ""
    catch {set here [current_scope]}
    puts "SAIF: entered scope '$c' (reports as '$here')"
    if {[catch {set try [get_objects -r *]} err2]} {
        puts "SAIF: get_objects in '$c' failed: $err2"
        continue
    }
    puts "SAIF: '$c' -> [llength $try] objects"
    if {[llength $try] > 0} {
        set objs $try
        set chosen $c
        break
    }
}

if {[llength $objs] == 0} {
    puts ""
    puts "SAIF NOT USABLE: no objects found in any DUT scope."
    puts "---- hierarchy dump, send this to Claude ----"
    catch {current_scope /}
    catch {report_scopes} r1 ; puts $r1
    catch {report_objects}  r2 ; puts $r2
    puts "---- end dump ----"
    quit
}

puts "SAIF: logging [llength $objs] objects from scope '$chosen'"
open_saif $saif
log_saif $objs
run all
close_saif

puts "SAIF written to $saif"
quit
