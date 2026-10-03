# =============================================================================
# board_program.tcl -- program the Basys3 over JTAG, no GUI.
#
#   vivado -mode batch -source syn/board_program.tcl -tclargs results/board/<name>.bit
#
# The board must be plugged in and powered (POWER switch on, JP1 jumper on
# JTAG or USB). Close any open Hardware Manager first -- only one client can
# hold the cable.
# =============================================================================
if {[llength $argv] != 1} { error "usage: -tclargs <bitfile>" }
set bit [file normalize [lindex $argv 0]]
if {![file exists $bit]} { error "no such bitstream: $bit" }

open_hw_manager
connect_hw_server -allow_non_jtag
open_hw_target
set dev [lindex [get_hw_devices xc7a35t*] 0]
if {$dev eq ""} { error "no xc7a35t on the JTAG chain -- is the board on?" }
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit $dev
program_hw_devices $dev
puts "PROGRAMMED [file tail $bit] -> $dev"
close_hw_target
disconnect_hw_server
close_hw_manager
