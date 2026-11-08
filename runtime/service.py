"""Audio-only supervisor. Launches no cores and handles no controller/video data."""
from pathlib import Path
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

BASE=Path(__file__).resolve().parent
STOP=False
CHILD=None
PID=Path('/tmp/mister-ethernet-audio.pid')
STATE=Path('/tmp/mister-ethernet-audio-status.json')


def terminate(signum,frame):
    global STOP
    STOP=True


def stop_child():
    global CHILD
    if CHILD is not None and CHILD.poll() is None:
        CHILD.terminate()
        try:CHILD.wait(timeout=5)
        except subprocess.TimeoutExpired:
            CHILD.kill();CHILD.wait()
    CHILD=None


def core_generation():
    try:
        p=Path('/tmp/CORENAME')
        return p.read_text().strip(),p.stat().st_mtime_ns
    except OSError:return '',0


def main():
    global CHILD
    with Path('/tmp/mister-ethernet-audio.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
        PID.write_text(str(os.getpid()))
        previous=None;last_attempt=0;last_state=None
        try:
            with Path('/tmp/mister-ethernet-audio.log').open('a',buffering=1) as log:
                while not STOP:
                    supported=json.loads((BASE/'cores.json').read_text())
                    generation=core_generation()
                    enabled=(BASE/'enabled').exists()
                    current=generation[0]
                    active=enabled and current in supported
                    if generation!=previous or not active:
                        stop_child();previous=generation;last_attempt=0
                    if active and (CHILD is None or CHILD.poll() is not None) and time.monotonic()-last_attempt>1:
                        stop_child();last_attempt=time.monotonic()
                        CHILD=subprocess.Popen([sys.executable,str(BASE/'send_audio.py'),
                            '--bind','169.254.93.225','--core',current,'--test-core',
                            '--continuous','--token-file',str(BASE/'auth.token'),
                            '--receipt','/tmp/mister-audio-last-session.json'],
                            stdout=log,stderr=log)
                    state={'enabled':enabled,'core':current,'supported':active,
                           'server_pid':CHILD.pid if CHILD and CHILD.poll() is None else None,
                           'phone_play':False}
                    if state!=last_state:
                        STATE.write_text(json.dumps(state)+'\n');last_state=state
                    time.sleep(.2)
        finally:
            stop_child()
            PID.unlink(missing_ok=True)
            STATE.write_text(json.dumps({'enabled':False,'stopped':True})+'\n')


if __name__=='__main__':main()
