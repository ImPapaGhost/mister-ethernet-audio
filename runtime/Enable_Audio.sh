#!/bin/sh
base=/media/fat/Scripts/EthernetAudio
touch "$base/enabled"
sh "$base/start.sh"
echo "Ethernet audio enabled for supported cores."
