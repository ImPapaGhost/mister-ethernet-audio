from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'runtime'))
from protocol import Decoder

ROOT=Path(__file__).resolve().parent.parent


class RealRTLStreams(unittest.TestCase):
    def setUp(self):
        self.stereo=bytes.fromhex((ROOT/'tests/PSX/normal.hex').read_text())
        self.mono=bytes.fromhex((ROOT/'tests/NES/normal.hex').read_text())

    def test_stereo_fragmentation(self):
        for size in (1,13,115,116,211,212,4096):
            d=Decoder();out=[]
            for offset in range(0,len(self.stereo),size):out+=d.feed(self.stereo[offset:offset+size])
            self.assertEqual([s for s,p in out],list(range(20)))
            self.assertEqual(b''.join(p for s,p in out),self.stereo)
            self.assertTrue(all(p[5]==2 for s,p in out))
            self.assertEqual(d.bad_crc,0)

    def test_unchanged_NES_stream(self):
        out=Decoder().feed(self.mono)
        self.assertEqual([s for s,p in out],list(range(20)))
        self.assertTrue(all(p[5]==1 and len(p)==116 for s,p in out))

    def test_mixed_packet_sizes(self):
        out=Decoder().feed(self.mono[:116]+self.stereo[:212]+self.mono[116:232])
        self.assertEqual([len(p) for s,p in out],[116,212,116])

    def test_right_channel_corruption_rejected(self):
        data=bytearray(self.stereo);data[3*212+18]^=1
        d=Decoder();out=d.feed(data)
        self.assertEqual([s for s,p in out],[i for i in range(20) if i!=3])
        self.assertEqual(d.bad_crc,1)

    def test_missing_byte_recovers(self):
        data=self.stereo[:3*212+48]+self.stereo[3*212+49:]
        self.assertEqual([s for s,p in Decoder().feed(data)],[i for i in range(20) if i!=3])

    def test_overload_keeps_complete_packets(self):
        data=bytes.fromhex((ROOT/'tests/PSX/overflow.hex').read_text())
        self.assertEqual([s for s,p in Decoder().feed(data)],[0,1,2,12])

    def test_invalid_channel_rejected(self):
        data=bytearray(self.stereo[:212]);data[5]=3
        out=Decoder().feed(data+self.stereo[212:])
        self.assertEqual([s for s,p in out],list(range(1,20)))


if __name__=='__main__':unittest.main()
