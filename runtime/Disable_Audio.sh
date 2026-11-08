#!/bin/sh
base=/media/fat/Scripts/EthernetAudio
rm -f "$base/enabled"
python3 "$base/control.py"
echo "Ethernet audio disabled."
