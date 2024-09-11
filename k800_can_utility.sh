#!/bin/bash
# Author: OnLogic 
# For:    K800 Reference Documentation
# Title:  Example Bash CAN Bus Utility
# Description:
#       This bash script provides a simple interface for CAN bus communication with the OnLogic Karbon 800
#       It allows sending and receiving CAN messages through the virtual CAN port.
#
#       Available bit-rates: 10     20     50     100    125    250    500    800    1000  Kbits/s
#
#       NOTE: THIS ONLY WORKS ON THE UBUNTU VARIANT OF THE K800 series.
# Usage: 
#       1. First, set permissions to be executable by user who owns file
#            chmod u+x k800_can_utility.sh
#
#       2. ./k800_can_utility.sh {s|r} <bit_rate> <led>
# Required packages:
#       sudo apt install can-utils  
# Examples:
#       ./k800_can_utility.sh s 100 off
#       ./k800_can_utility.sh r 20 on
#       ./k800_can_utility.sh r  # Uses default bit_rate and no LED check
# IMPORTANT:  
#       MAKE SURE TO REPLACE PASSWORD WITH THE SYSTEM PASSWORD
#       This script requires admin and password privileges
# NOTE: 
#     If switching CAN bit_rates successively between sessions, 
#     and are having difficulty in doing so, attempt resetting the microcontroller:
#         1. go to the putty terminal (make sure to do so with sudo privileges in ubuntu)
#         2. type in 'reset' into the terminal
#         3. wait 10 seconds
#     And try again.
#     There may also be issues turning off all the onboard leds after LED check,
#     A reset would help that as well, fundementally, the python version of this
#     script is more stable because it has better access to low level system components

ADMIN_PASSWORD="password"
emcu_input=$(ls -l /dev/serial/by-id/ | awk '/usb-OnLogic/ {sub(".*/","",$NF); if(++count==1) {print "/dev/"$NF; exit}}')
emcu_can=$(ls -l /dev/serial/by-id/ | awk '/usb-OnLogic/ {sub(".*/","",$NF); if(++count==2) {print "/dev/"$NF; exit}}')

mode="r"

bit_rate='s8'

# declare associative array of bitrates mapping bitrates with the correct parameters for slcand
declare -A bitrates
bitrates[10]='s0'
bitrates[20]='s1'
bitrates[50]='s2'
bitrates[100]='s3'
bitrates[125]='s4'
bitrates[250]='s5'
bitrates[500]='s6'
bitrates[750]='s7'
bitrates[1000]='s8'

led_check="off"

# Parse command-line arguments, default if command line input is not valid
if [ "$1" == "r" ] || [ "$1" == "s" ]; then
    mode="$1"
else
    echo "ATTENTION: invalid mode, using default"
fi

# Check if bitrate is valid.
case "$2" in
    10|20|50|100|125|250|500|750|1000)
        bit_rate=${bitrates["$2"]} 
        ;;
    *)
        echo "ATTENTION: invalid bit-rate, using default: 1000kbit/sec"
        ;;
esac

# check led param
if [ "$3" == "on" ] || [ "$3" == "off" ]; then
    led_check="$3"
else
    echo "LED check defaulting to false"
fi

# toggle on and off leds to verify MCU connection
cntrl_all_leds() {
    local state=$1
    local led_check=$2  
    if [ "$led_check" != "on" ]; then
        return
    fi 
    sleep 1s
    echo "Setting all LEDs to $state"
    printf "\r\n" > $emcu_input
    for i in {0..3}; do
        printf "dio set LED0 $i $state\r\n" > $emcu_input
        sleep 1
    done
    printf "\r\n"> $emcu_input
}

# cleanup function to close buffer and shot can down
cleanup() {
    echo -e "\nCleaning up..."
    echo $ADMIN_PASSWORD | timeout .5 cat $emcu_input >/dev/null
    sleep 2
    cntrl_all_leds false $led_check
    echo $ADMIN_PASSWORD | sudo -S ifconfig vcan0 down 2> /dev/null
    echo $ADMIN_PASSWORD | sudo -S pkill scand
    echo "Cleanup complete."
    exit 0
}

# Set trap for Ctrl+C
trap cleanup SIGINT

# check vid, pid
echo $ADMIN_PASSWORD | sudo -S sh -c "dmesg" | grep 'idVendor=353f, idProduct=a101'
if [ $? == 0 ]; then
   echo "vid pid OK"
else
   echo "vid pid NOT OK"
   # if vid, pid do not match, exit here
   cntrl_all_leds false $led_check
   exit 0
fi

# make ttyACM0 read/write
# echo "Password Received: ADMIN_PASSWORD = " ${ADMIN_PASSWORD} # uncomment for verification
echo $ADMIN_PASSWORD | sudo -S chmod a+rw $emcu_input

# wait for eMCU uart to be ready
stty -F $emcu_input 115200 min 0 -brkint -icrnl -imaxbel -opost -onlcr -isig -icanon -iexten -echo -echoe -echok -echoctl -echoke

tail -f $emcu_input &  # read and wait forever
printf '\r\n' > $emcu_input
printf 'history\n' > $emcu_input
sleep 2s
killall tail               

# open all led in eMCU
cntrl_all_leds true "$led_check"

# setup eMCU's can act as vcan
echo "Setup vcan"
printf 'set can-mode VCAN0 slcan\n' > $emcu_input 
sleep 0.5

# Now use slcan daemon to create new a can iterface, as vcan0
# NOTE: in slcan, bitrate and follows the key-value pair previously described
# for s0-s8 defined in the associative array 
echo $ADMIN_PASSWORD | sudo -S slcand -o -c -${bit_rate} $emcu_can vcan0 
sleep 0.01
echo $ADMIN_PASSWORD | sudo -S ifconfig vcan0 up
sleep 0.01
echo $ADMIN_PASSWORD | sudo -S ifconfig vcan0 txqueuelen 1000
sleep 0.01

# Check if can interface is up
ip link show dev vcan0 | grep 'vcan0' &> /dev/null
if [ $? == 0 ]; then
   echo "vcan0 OK"
else
   echo "vcan0 NOT OK"
   cleanup
fi

# run candump or can send, depending on what was chosen
echo "Run CAN Operations"
if [ "$mode" == "r" ]; then
    echo "Starting candump (Press Ctrl+C to stop)"
    candump -x vcan0
else
    echo "Starting cansend (Press Ctrl+C to stop)"
    x=1
    while true; do
        echo "Now: $x "
        cansend vcan0 01a#11223344AABBCCDD
        sleep 1
        x=$(( $x + 1 ))
    done
fi

cleanup
