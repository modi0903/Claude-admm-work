`timescale 1ns / 1ps
// Minimal 8N1 UART transmitter. No FIFO, no parity -- assert start for one
// cycle with data valid, wait for busy to fall. CLK_HZ must match the clock
// actually driving this module, NOT the 100 MHz oscillator.
module uart_tx #(
    parameter integer CLK_HZ = 50_000_000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,
    input  wire [7:0] data,
    output reg        tx,
    output wire       busy
);
    localparam integer DIV = CLK_HZ / BAUD;   // 434 at 50 MHz / 115200
    reg [15:0] cnt = 16'd0;
    reg [3:0]  bit_i = 4'd0;
    reg [9:0]  sr = 10'h3FF;
    reg        active = 1'b0;
    assign busy = active;

    always @(posedge clk) begin
        if (!rst_n) begin
            tx <= 1'b1; active <= 1'b0; cnt <= 16'd0; bit_i <= 4'd0;
            sr <= 10'h3FF;
        end else if (!active) begin
            tx <= 1'b1;
            if (start) begin
                sr     <= {1'b1, data, 1'b0};   // stop, data LSB-first, start
                active <= 1'b1;
                cnt    <= 16'd0;
                bit_i  <= 4'd0;
            end
        end else begin
            if (cnt == DIV[15:0] - 16'd1) begin
                cnt <= 16'd0;
                tx  <= sr[0];
                sr  <= {1'b1, sr[9:1]};
                if (bit_i == 4'd9) active <= 1'b0;
                else bit_i <= bit_i + 4'd1;
            end else cnt <= cnt + 16'd1;
        end
    end
endmodule
