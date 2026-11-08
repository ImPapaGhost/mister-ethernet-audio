`timescale 1ns/1ps
module audio_uart_tb;
    parameter integer BAUD=3125000;
    localparam real BIT_NS=1000000000.0/BAUD;
    reg clk=0, reset=1, valid=0;
    reg [31:0] sample=0;
    wire tx;
    wire [31:0] dropped;
    reg generating=1;
    integer cycle_count=0, sample_count=0, file_handle, n;
    reg [7:0] received;
    string output_name;
    always #20.3450520833 clk=~clk;
    audio_uart #(.BAUD_HZ(BAUD)) dut(clk,reset,valid,sample,tx,dropped);
    always @(negedge clk) begin
        valid=0;
        if(reset) begin cycle_count=0;sample_count=0;end
        else if(generating) begin
            if(cycle_count==511) begin
                cycle_count=0;valid=1;sample[15:0]=(sample_count*73)^16'h5a5a;sample[31:16]=(sample_count*19)^16'hb6b6;sample_count=sample_count+1;
            end else cycle_count=cycle_count+1;
        end
    end
    initial begin
        if(!$value$plusargs("OUT=%s",output_name)) output_name="uart.hex";
        file_handle=$fopen(output_name,"w");
        #1000;reset=0;
        #20000000;generating=0;
        #40000000;
        $display("INPUT_SAMPLES=%0d DROPPED_BLOCKS=%0d BAUD=%0d",sample_count,dropped,BAUD);
        if(BAUD==3125000 && dropped!=0) $fatal(1,"Unexpected overflow at production rate");
        if(BAUD==200000 && dropped==0) $fatal(1,"Overflow test did not overflow");
        $fclose(file_handle);$finish;
    end
    initial begin
        wait(!reset);
        forever begin
            @(negedge tx);
            #(BIT_NS*1.5);
            for(n=0;n<8;n=n+1) begin
                received[n]=tx;#(BIT_NS);
            end
            if(tx!==1'b1) $fatal(1,"Invalid UART stop bit");
            $fwrite(file_handle,"%02x\n",received);
        end
    end
endmodule
