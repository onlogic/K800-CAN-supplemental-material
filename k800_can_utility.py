"""
Author: OnLogic
For:    K800 Reference Documentation
Title:  K800 Example Python CAN Bus Utility

Description:
    This Python script provides a simple interface for CAN bus communication with the OnLogic Karbon 800
    It allows sending and receiving CAN messages through the virtual CAN port.
    
    For more examples and instructions on how to modify the following code, see the 

    https://python-can.readthedocs.io/en/v4.3.0/api.html

    Available bit-rates: 
        10     20     50     100    125    250    500    800    1000  Kbits/s

Dependencies:
    1. pyserial: 
        pip install pyserial
    2. python-can: 
        pip install python-can

Usage:
    1. Using command-line arguments:
       Windows: python k800_can_utility.py [-h] [-m {s,r}] [-b {10,20,50,100,125,250,500,750,1000}] [-l {off,on}]
       Linux:   sudo python3 k800_can_utility.py [-h] [-m {s,r}] [-b {10,20,50,100,125,250,500,750,1000}] [-l {off,on}]

    2. Using regular variables (edit the script):
       Set USE_ARGPARSE to False and modify DEFAULT_MODE and DEFAULT_BITRATE
       
        IF you want to get rid of command line arguments entirely, remove this:
        "
        if USE_ARGPARSE:
            args     = parse_arguments()
            mode     = args.mode
            bit_rate = args.bit_rate
            is_led   = args.leds
        else:
        "

Examples:
    Windows:
        python k800_can_utility.py -m s -b 500 -l on
        python k800_can_utility.py -m r
        
    Linux:
        sudo python3 k800_can_utility.py -m r -b 1000 -l off
        sudo python3 k800_can_utility.py -m s
NOTE: 
    If you are switching CAN bauds successively between sessions, 
    and are having difficulty in doing so, attempt resetting the microcontroller:
        1. go to the putty terminal (make sure to do so with sudo privileges in ubuntu)
        2. type in 'reset' into the terminal
        3. wait 10 seconds
    And try again
"""

import serial
from serial.tools import list_ports as system_ports
import can
import time
import sys
import argparse
from datetime import datetime

'''---------------- Global Variables ----------------'''
# Vendor ID and Product ID assigned by MCU vendor
MCU_VID_PID = '353F:A101'

# True for command-line, False to use regular variables in main
USE_ARGPARSE = True  # default to CMD

# Default values (used when USE_ARGPARSE is False)
DEFAULT_MODE     = 's'   # 's', send or 'r', receive
DEFAULT_BITRATE  = 1000  # baud in kbps
valid_bit_rates  = [10, 20, 50, 100, 125, 250, 500, 750, 1000]
LED_CHECK        = 'off' # whether to initialte led check or not,
                         # 'off' or 'on'
'''--------------------------------------------------'''

def inc_dec_data_string(low=0, high=9):
    """Generate oscillating data string for debugging."""
    global number, is_increment
    if number == low:
        is_increment = True
    elif number == high:
        is_increment = False

    number += 1 if is_increment else -1
    return f'K800_{number}'


def set_led_status(port, is_led=False, status=True):
    """Sequentially turn 4 on-board LEDs on or off, useful connection check."""
    LED_COUNT = 4
    if is_led == 'off' or not port:
        return
    for i in range(LED_COUNT):
        command = f'dio set LED0 {i} {str(status).lower()}\r\n'
        port.write(command.encode())
        time.sleep(0.1)


def configure_can(port, interface, mode, baud):
    """CAN interface issued to MCU via command line."""
    port.write(f'set can-mode {interface} {mode}\r\n'.encode())
    time.sleep(0.1)
    port.write(f'set can-baudrate {interface} {baud}\r\n'.encode())
    time.sleep(0.1)
    print(port.read(port.inWaiting()).decode())


def get_device_port(dev_id, location=None):
    """Scan and return the port of the target device."""
    all_ports = system_ports.comports() 
    for port in sorted(all_ports):
        if dev_id in port.hwid:
            if location and location in port.location:
                print(f'Port: {port}\nPort Location: {port.location}\nHardware ID: {port.hwid}\nDevice: {port.device}')
                print('*'*15)
                return port.device
    return None


def parse_arguments():
    """Receive and parse command-line arguments."""
    parser = argparse.ArgumentParser(description="K800 CAN Bus Utility")
    parser.add_argument('-m', '--mode', choices=['s', 'r'], help="send (s) or receive (r): send generated data or continually receive")
    parser.add_argument('-b', '--bitrate', choices=valid_bit_rates, 
                        help=f"CAN bus baudrate in kbps (ranges allowed by slcan: \
                        {valid_bit_rates}", type=int, default=DEFAULT_BITRATE)
    parser.add_argument('-l', '--leds', choices=['off', 'on'], help="Incorporate LED check functionality in program", default=LED_CHECK)
    return parser.parse_args()

def main():
    '''main, implementation of session logic.'''
    if USE_ARGPARSE:
        args     = parse_arguments()
        mode     = args.mode
        bit_rate = args.bitrate
        is_led   = args.leds
    else:
        mode     = DEFAULT_MODE
        bit_rate = DEFAULT_BITRATE
        is_led   = LED_CHECK

    if bit_rate not in valid_bit_rates:
        print(f"Error: Invalid bit_rate. Please enter a value between 1 and 1000 kbps.")
        sys.exit(1)

    # Get and open Management port, main serial port at baud 9600
    # (equivalent to Putty terminal)
    mgmt_port = get_device_port(MCU_VID_PID, ".0")
    vcan_port = get_device_port(MCU_VID_PID, ".2")

    if not mgmt_port or not vcan_port:
        print("Error: K800 MCU not found. Please check configurations and connections.")
        sys.exit(1)

    port = serial.Serial(mgmt_port)

    # Write NL to the serial terminal
    port.write(b'\r\n')
    time.sleep(0.1)

    # Show terminal content
    port.read(port.inWaiting())

    # Configure virtualized CAN port  
    print("Configuring CAN port...")
    configure_can(port, 'VCAN0', 'slcan', str(bit_rate))

    set_led_status(port, is_led, status=True)

    # Init and create bus using slcan interface on selected vcan_port 
    bus = can.Bus(interface='slcan', channel=vcan_port, bitrate=bit_rate*1000, receive_own_messages=False)

    # DEFAULT MESSAGE FORMAT: Pass custom data into the data field and use in loop for custom implementations  
    # message = can.Message(arbitration_id=123, is_extended_id=True, data=[0x12, 0x22, 0x33]) 
    print (
        f"Starting CAN bus {'transmission' if mode == 's' else 'reception'}...\n"
        "Ctrl+C to exit"
    )

    # variables for example can bus generation
    # can be removed/replaced with custom implementaiton
    global number, is_increment
    number = 0
    is_increment = True

    try:
        while True:
            if mode == 's':
                # generate data string
                data = inc_dec_data_string()
                
                # Get the current time to add to can frame report
                msg_time = datetime.now().timestamp()

                # encode as bytes, transmitting in specified frame format
                message = can.Message(timestamp=msg_time, arbitration_id=0x123, is_extended_id=True, data=data.encode('utf-8'))
                
                # send message
                bus.send(message, timeout=0.2)

                # print with small delay after send attempt
                print(f"Sent: {message}")
                time.sleep(0.1)
            else:
                # poll for input then print if recieved a msg
                received_msg = bus.recv()
                print(f"Received: {received_msg}")
    except KeyboardInterrupt:
        print("\nOperation terminated by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        time.sleep(1)
        port.reset_input_buffer()
        port.reset_output_buffer()
        set_led_status(port, is_led, status=False)
        bus.shutdown()
        port.close()

if __name__ == '__main__':
    main()