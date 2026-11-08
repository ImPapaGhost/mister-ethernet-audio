from pathlib import Path
import json
import struct
import zlib

reports = []
for scenario in ('normal', 'overflow'):
    data = bytes.fromhex(Path(scenario + '.hex').read_text())
    assert len(data) % 116 == 0
    sequences = []
    for offset in range(0, len(data), 116):
        packet = data[offset:offset+116]
        magic, version, channels, count, sequence, rate = struct.unpack('<4sBBHII', packet[:16])
        assert (magic, version, channels, count, rate) == (b'MAUD', 1, 1, 48, 48000)
        assert zlib.crc32(packet[:-4]) == struct.unpack('<I', packet[-4:])[0]
        expected = [(((sequence*48+i)*73) ^ 0x5a5a) & 65535 for i in range(48)]
        assert list(struct.unpack('<48H', packet[16:-4])) == expected
        sequences.append(sequence)
    assert sequences == sorted(set(sequences))
    if scenario == 'normal':
        assert sequences == list(range(20))
    else:
        assert any(b > a+1 for a, b in zip(sequences, sequences[1:]))
    reports.append({'scenario': scenario, 'packets': len(sequences), 'sequences': sequences,
                    'CRC_and_samples_valid': True})
Path('verification.json').write_text(json.dumps(reports, indent=2)+'\n', encoding='utf-8')
print(json.dumps(reports))
