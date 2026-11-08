import struct
import zlib

HEADER = struct.Struct('<4sBBHII')
MAX_SIZE = 212


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_crc = 0

    def feed(self, data):
        self.buffer.extend(data)
        packets = []
        while len(self.buffer) >= HEADER.size:
            pos = self.buffer.find(b'MAUD')
            if pos < 0:
                del self.buffer[:-3]
                break
            if pos:
                del self.buffer[:pos]
            if len(self.buffer) < HEADER.size:
                break
            magic, version, channels, frames, sequence, rate = HEADER.unpack_from(self.buffer)
            if version != 1 or channels not in (1, 2) or frames != 48 or rate != 48000:
                del self.buffer[0]
                continue
            size = HEADER.size + frames*channels*2 + 4
            assert size <= MAX_SIZE
            if len(self.buffer) < size:
                break
            packet = bytes(self.buffer[:size])
            if zlib.crc32(packet[:-4]) != struct.unpack_from('<I', packet, size-4)[0]:
                self.bad_crc += 1
                del self.buffer[0]
                continue
            packets.append((sequence, packet))
            del self.buffer[:size]
        return packets
