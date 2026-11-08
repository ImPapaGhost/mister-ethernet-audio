from pathlib import Path
import os
import signal

base=Path(__file__).resolve().parent
pidfile=Path('/tmp/mister-ethernet-audio.pid')
if pidfile.exists():
    pid=int(pidfile.read_text())
    command=Path('/proc')/str(pid)/'cmdline'
    if command.exists() and str(base/'service.py').encode() in command.read_bytes():
        os.kill(pid,signal.SIGTERM)
