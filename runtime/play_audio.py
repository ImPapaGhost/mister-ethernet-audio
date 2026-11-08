"""Receive test-core audio directly; no picture capture or controller transport."""
import argparse
import json
from pathlib import Path
import socket
import threading
import time
import numpy as np
import sounddevice as sd
from protocol import Decoder


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='169.254.93.225')
    p.add_argument('--port', type=int, default=55241)
    p.add_argument('--token-file', required=True)
    p.add_argument('--receipt')
    p.add_argument('--seconds', type=int, default=120)
    p.add_argument('--device-name', default='Sonos Roam SL')
    p.add_argument('--buffer-ms',type=int,default=6)
    p.add_argument('--max-buffer-ms',type=int,default=24)
    p.add_argument('--continuous',action='store_true')
    p.add_argument('--quiet',action='store_true')
    p.add_argument('--stop-file')
    p.add_argument('--status-file')
    args = p.parse_args(argv)
    assert args.host.startswith('169.254.') and 1 <= args.seconds <= 300
    assert 5<=args.buffer_ms<args.max_buffer_ms<=150
    target_bytes=args.buffer_ms*48*4
    maximum_bytes=args.max_buffer_ms*48*4
    devices = [(i, d) for i, d in enumerate(sd.query_devices())
               if args.device_name in d['name'] and d['max_output_channels'] >= 2
               and sd.query_hostapis(d['hostapi'])['name'] == 'Windows WASAPI']
    assert len(devices) == 1, 'Expected one matching WASAPI speaker: '+repr(devices)
    device, details = devices[0]
    sd.check_output_settings(device=device, channels=2, dtype='int16', samplerate=48000)
    queue = bytearray();guard = threading.Lock();ended = threading.Event();ready = threading.Event()
    stats = {'packets': 0, 'sequence_gaps': 0, 'bad_crc': 0, 'underflow_frames': 0,
             'discarded_old_frames': 0, 'peak_pcm': 0, 'changed_samples': 0,
             'receiver_error': None, 'output_device': details['name'],
             'buffer_target_ms':args.buffer_ms,'buffer_max_ms':args.max_buffer_ms,
             'complete_acoustic_delay_measured': False}
    token = Path(args.token_file).read_text().strip().encode('ascii');assert len(token) == 64
    decoder = Decoder()

    def callback(outdata, frames, times, status):
        needed = frames*4
        with guard:
            data = bytes(queue[:needed]);del queue[:needed]
            stats['underflow_frames'] += (needed-len(data))//4
        outdata[:] = data + b'\0'*(needed-len(data))

    def receive():
        previous = None
        try:
            with socket.create_connection((args.host, args.port), timeout=10) as client:
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client.sendall(token);client.settimeout(1)
                until = time.monotonic()+args.seconds
                last_valid=time.monotonic()
                while not ended.is_set() and (args.continuous or time.monotonic()<until):
                    if args.stop_file and Path(args.stop_file).exists():break
                    try:
                        data=client.recv(4096)
                    except socket.timeout:
                        if time.monotonic()-last_valid>6:
                            raise RuntimeError('No valid audio packets for6s')
                        continue
                    if not data:break
                    for sequence, packet in decoder.feed(data):
                        last_valid=time.monotonic()
                        if previous is not None:
                            gap=(sequence-previous-1)&0xffffffff
                            stats['sequence_gaps'] += gap if gap < 100000 else 0
                        previous=sequence
                        channels=packet[5]
                        pcm=np.frombuffer(packet[16:-4],dtype='<i2').reshape(48,channels)
                        stats['peak_pcm']=max(stats['peak_pcm'],int(np.max(np.abs(pcm.astype(np.int32)))))
                        stats['changed_samples']+=int(np.count_nonzero(pcm[1:] != pcm[:-1]))
                        stats['channels_received']=channels
                        stereo=np.repeat(pcm[:,0],2).tobytes() if channels==1 else pcm.tobytes()
                        with guard:
                            queue.extend(stereo)
                            if len(queue)>maximum_bytes:
                                keep=target_bytes
                                stats['discarded_old_frames']+=(len(queue)-keep)//4
                                del queue[:-keep]
                            if len(queue)>=target_bytes:ready.set()
                        stats['packets']+=1
                stats['bad_crc']=decoder.bad_crc
        except Exception as e:stats['receiver_error']=str(e)
        finally:
            stats['bad_crc']=decoder.bad_crc
            ended.set();ready.set()

    thread=threading.Thread(target=receive,daemon=True);thread.start()
    assert ready.wait(15), 'No audio received'
    if not stats['packets']:raise RuntimeError('No PCM received: '+str(stats))
    try:
        with sd.RawOutputStream(device=device,samplerate=48000,channels=2,dtype='int16',
                                blocksize=240,latency='low',callback=callback) as stream:
            stats['reported_output_latency_seconds']=stream.latency
            print('Output:',details['name'],'PortAudio output latency:',stream.latency,
                  '(does not measure complete Bluetooth/acoustic delay)',flush=True)
            while not ended.wait(1):
                with guard:queued_ms=len(queue)/4/48000*1000
                if args.status_file:
                    Path(args.status_file).write_text(json.dumps({'state':'playing',
                        'channels':stats.get('channels_received'),
                        'packets':stats['packets'],'updated':time.time(),
                        'queue_ms':round(queued_ms,1),'phone_play':False})+'\n',encoding='utf-8')
                if not args.quiet:
                    print('Audio packets:',stats['packets'],'app queue ms:',round(queued_ms,1),flush=True)
    finally:
        ended.set();thread.join(2)
        if args.receipt:
            Path(args.receipt).write_text(json.dumps(stats,indent=2)+'\n',encoding='utf-8')
        print(stats,flush=True)


if __name__ == '__main__':
    main()
