#!/bin/sh
base=/media/fat/Scripts/EthernetAudio
nohup python3 "$base/service.py" >/tmp/mister-audio-supervisor-launch.log 2>&1 </dev/null &
