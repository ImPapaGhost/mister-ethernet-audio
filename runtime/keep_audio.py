"""User-session receiver: reconnects automatically and stays idle in menus."""
from pathlib import Path
import contextlib
import ctypes
from ctypes import wintypes
import json
import sys
import time
import traceback
import play_audio

BASE=Path(__file__).resolve().parent


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateMutexW.restype=wintypes.HANDLE
    handle=kernel.CreateMutexW(None,False,'Local\\MiSTerEthernetAudio')
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:return
    stop=BASE/'stop.flag';last_message=None
    try:
        while not stop.exists():
            log=BASE/'receiver.log'
            if log.exists() and log.stat().st_size>1024*1024:
                old=BASE/'receiver.previous.log'
                log.replace(old)
            with log.open('a',encoding='utf-8',buffering=1) as stream:
                try:
                    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                        play_audio.main(['--continuous','--quiet','--host','169.254.93.225',
                            '--token-file',str(BASE/'auth.token'),'--stop-file',str(stop),
                            '--receipt',str(BASE/'last-session.json'),
                            '--status-file',str(BASE/'status.json'),
                            '--buffer-ms','20','--max-buffer-ms','60'])
                    message='waiting for next supported game'
                except Exception as error:
                    message=str(error)
                    if '10061' in message or 'Connection refused' in message:
                        message='waiting for NES or PlayStation audio'
                    if message!=last_message:
                        stream.write(time.strftime('%Y-%m-%d %H:%M:%S ')+message+'\n')
                (BASE/'status.json').write_text(json.dumps({'state':message,
                    'updated':time.time(),'phone_play':False})+'\n',encoding='utf-8')
                last_message=message
            time.sleep(1)
    finally:
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(handle)


if __name__=='__main__':main()
