"""Bounded audio-only server for isolated NES/PSX test cores. Linux/ARM Python3."""
import argparse
import fcntl
import hmac
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import termios
import time
from protocol import Decoder

TCGETS2 = 0x802C542A
TCSETS2 = 0x402C542B
BOTHER = 0x1000


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bind', default='169.254.93.225')
    p.add_argument('--port', type=int, default=55241)
    p.add_argument('--seconds', type=int, default=120)
    p.add_argument('--token-file', required=True)
    p.add_argument('--receipt')
    p.add_argument('--test-core', action='store_true', required=True)
    p.add_argument('--core',choices=('NES','PSX'),required=True)
    p.add_argument('--continuous',action='store_true')
    args = p.parse_args()
    assert args.bind.startswith('169.254.'), 'This prototype is restricted to the direct Ethernet link'
    assert 1 <= args.seconds <= 300
    wire_baud = 3125000 if args.core == 'PSX' else 2083333
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    os.nice(10)
    token = Path(args.token_file).read_text().strip().encode('ascii')
    assert len(token) == 64 and all(chr(c) in '0123456789abcdef' for c in token)
    decoder = Decoder()
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.bind, args.port));server.listen(1);server.settimeout(30)
        print('Waiting for authenticated audio receiver', flush=True)
        try:
            connection,peer=server.accept()
        except socket.timeout:
            return
        with connection:
            assert peer[0].startswith('169.254.')
            connection.settimeout(5)
            received = bytearray()
            while len(received) < 64:
                piece = connection.recv(64-len(received))
                if not piece:raise RuntimeError('Receiver disconnected during handshake')
                received.extend(piece)
            assert hmac.compare_digest(received, token), 'Invalid receiver token'
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            connection.settimeout(.1)
            fd = os.open('/dev/ttyS1', os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
            # Preserve the exact custom baud too; normal tcgetattr only exposes
            # the BOTHER flag for nonstandard rates such as MIDI31250.
            before = bytearray(44)
            fcntl.ioctl(fd, TCGETS2, before, True)
            count = 0
            started = time.monotonic()
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                info = bytearray(128);fcntl.ioctl(fd, 0x541E, info, True)
                assert struct.unpack_from('i', info, 28)[0] == 6250000, 'Unexpected UART clock; do not use this test bitstream'
                settings = bytearray(before)
                struct.pack_into('=4I', settings, 0, 0, 0,
                                 termios.CLOCAL | termios.CREAD | termios.CS8 | BOTHER, 0)
                settings[17+termios.VMIN] = settings[17+termios.VTIME] = 0
                struct.pack_into('=2I', settings, 36, wire_baud, wire_baud)
                fcntl.ioctl(fd, TCSETS2, settings)
                termios.tcflush(fd, termios.TCIFLUSH)
                started = last_valid = time.monotonic();count = 0
                last_core_check = started
                while args.continuous or time.monotonic()-started < args.seconds:
                    if time.monotonic()-last_core_check > .25:
                        if Path('/tmp/CORENAME').read_text().strip() != args.core:
                            print('Core changed; stopping audio', flush=True)
                            break
                        last_core_check = time.monotonic()
                    if select.select([fd], [], [], .02)[0]:
                        try:
                            incoming = os.read(fd, 4096)
                        except BlockingIOError:
                            continue
                        for sequence, packet in decoder.feed(incoming):
                            connection.sendall(packet);count += 1;last_valid = time.monotonic()
                    if time.monotonic()-last_valid > 5:
                        raise RuntimeError('No valid test-core PCM packets for5s; stopping')
                print('Audio packets sent:', count, 'bad CRC:', decoder.bad_crc, flush=True)
            except (BrokenPipeError, ConnectionResetError):
                print('Receiver disconnected; stopping audio', flush=True)
            finally:
                fcntl.ioctl(fd, TCSETS2, before)
                restored = bytearray(44)
                fcntl.ioctl(fd, TCGETS2, restored, True)
                os.close(fd)
                result = {'packets_sent': count, 'bad_crc': decoder.bad_crc,
                          'elapsed_seconds': time.monotonic()-started,
                          'serial_attributes_restored': restored == before,
                          'transport': 'audio-only TCP over direct Ethernet'}
                result['core']=args.core
                if args.receipt:
                    Path(args.receipt).write_text(json.dumps(result, indent=2)+'\n')
                print(result, flush=True)
                assert restored == before, 'Serial settings did not restore exactly'


if __name__ == '__main__':
    main()
