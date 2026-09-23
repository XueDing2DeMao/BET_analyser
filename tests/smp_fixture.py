"""构造独立的 SMP 二进制样本；只含公开合成等温线。"""
import struct
from pathlib import Path
import numpy as np
from bet_analysis import read_bet_xls

TUBE_HEX = (
    "0100000000000000f03f00000000000002000000000000f03f000000000000f03f"
    "000000000000f03f000000000000f03f000000000000f03f000000000000f03f"
    "000000000000f03f000000000000f03f000000000000f03f000000000000f03f"
    "000000000000f03f000000000000f03f000000000000f03f0100000000000000f03f"
    "000000000000f03f000000000000000000000100000000000000000000000000000000"
    "00c087400000000001000100690076000000000000000000000000000000000000000000"
)


def string(value):
    encoded = (value + '\0').encode('utf-16le') if value else b''
    return b'\xe0\x01\x00' + struct.pack('<I', len(encoded)) + encoded


def sample_info(mass, name):
    data = b'\x13\x00\x00' + string(name) + string('') * 3
    data += bytes(4) + b'\x01\x00'
    data += b''.join(string(s) for s in ('Sample:', 'Operator:', 'Submitter:', 'Bar Code:', ''))
    return data + b'\x01\x01\x00\x00\x00' + struct.pack('<dddd', mass, 50., 51., 1.)


def record(values, *, minutes=0, previous=0.):
    data = b'\xe0' + struct.pack('<d', float('nan')) + b'\x05\x00'
    data += struct.pack('<dddH', *values, minutes) + bytes(3)
    return data + struct.pack('<d', previous) + bytes(16) + b'\x05\x00'


def conditions(n_ads, p0, *, coefficients, tube_id):
    tail = struct.pack('<IIBddd', 1, n_ads, 7, 760., 760., 77.3)
    tail += (b'\x01' + bytes(14)) * 3 + b'\x01'
    tail += struct.pack('<I', len(p0)) + bytes(10)
    tail += b''.join(struct.pack('<dH', p, i) for i, p in enumerate(p0))
    tail += b'\x05' + bytes(7) + struct.pack('<dBI', 298., 2, 2)
    tail += struct.pack('<dddd', 750., 77., 800., 78.)
    tail += b'\x01' + bytes(14) + b'\x07'
    tail += struct.pack('<ddddd', 45., 16., 6.2e-5, 64., 20.)
    tube = bytearray.fromhex(TUBE_HEX)
    struct.pack_into('<d', tube, 139, 6.2e-5)
    tube[178:182] = tube_id.encode('utf-16le')
    tail += b'\x05' + string('Synthetic tube') + tube
    return tail + struct.pack('<Hdd', 1, *coefficients)


def measurement(source, *, mass, coefficients, measurement_id, prior_mode, tube_id):
    values = np.vstack((source['ads'], source['des'][1:]))
    p = values[:, 0] * 760.
    bath = (64. - 20.) / (1 - 77.3 / 298.)
    free = p / 760 * (64. - bath * coefficients[0] + p * 6.2e-5 * bath * (1-coefficients[1]))
    doses = values[:, 1] * mass + free
    data = b'\x0d\xe0\x03\x00\x09\x01\x00' + struct.pack('<H', measurement_id)
    data += string('ASAP 2460 Version 3.01') * 2 + string('SYNTHETIC')
    data += bytes(64) + b'\x03\x07' + struct.pack('<I', len(p))
    data += record((0., 0., 0.))
    for i, (pressure, relative, dose) in enumerate(zip(p, values[:, 0], doses), 1):
        previous = values[i-2, 0] if prior_mode == 'chain' and i > 1 else 0.
        data += record((pressure, relative, dose), minutes=i, previous=previous)
    return data + conditions(
        len(source['ads']), np.full(len(p)+1, 760.),
        coefficients=coefficients, tube_id=tube_id,
    )


def container(sections, *, padding=0):
    directory_size = 3 + 10 * len(sections)
    offset = 32 + 18 + directory_size + padding
    directory, body = bytearray(), bytearray(padding)
    for key, payload in sections.items():
        directory += struct.pack('<HII', key, offset, len(payload))
        header = f'SUBSET{key}'.encode().ljust(10, b'\0')
        body += header + struct.pack('<HHI', 0, key, len(payload)) + payload
        offset += 18 + len(payload)
    header = b'^vMIC##&&FS\x000200' + bytes(8) + struct.pack('<II', 32, directory_size)
    index = b'SUBSET101\0' + struct.pack('<HHI', 0, 101, directory_size)
    return header + index + struct.pack('<BH', 2, len(sections)) + directory + body


def make_smp(*, mass=.5, name='Synthetic', padding=0, coefficients=(.002, .05),
             measurement_id=1, prior_mode='chain', tube_id='iv'):
    source = read_bet_xls(str(Path(__file__).parents[1] / 'examples/reference_mesoporous.xlsx'))
    source['des'][0] = source['ads'][-1]  # SMP 两支共用一次实际测量的转折点。
    gas = b'\x0f' + string('Nitrogen') + string('N2')
    gas += struct.pack('<HdHdddd', 0, 925., 0, 6.2e-5, .0015468, 3.86, .162)
    sections = {301: sample_info(mass, name), 337: gas}
    sections[303] = measurement(
        source, mass=mass, coefficients=coefficients,
        measurement_id=measurement_id, prior_mode=prior_mode, tube_id=tube_id,
    )
    return container(sections, padding=padding), source
