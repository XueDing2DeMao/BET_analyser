"""原生 SMP 入口、参数还原与拒绝错误布局。"""
import struct
import numpy as np
import pytest
from bet_analysis import read_bet_xls
from tests.smp_fixture import make_smp


def read_bytes(tmp_path, data):
    path = tmp_path / 'arbitrary-name.SMP'
    path.write_bytes(data)
    return read_bet_xls(str(path))


@pytest.mark.parametrize('mass,padding,name', [(.5, 0, 'Synthetic'), (1.2, 43, '不同长度的样品名')])
def test_native_smp_restores_both_branches(tmp_path, mass, padding, name):
    data, source = make_smp(mass=mass, padding=padding, name=name)
    actual = read_bytes(tmp_path, data)
    np.testing.assert_array_equal(source['ads'][:, 0], actual['ads'][:, 0])
    np.testing.assert_allclose(source['ads'], actual['ads'], rtol=1e-12)
    np.testing.assert_allclose(source['des'], actual['des'], rtol=1e-12)
    assert False is actual['summary']['instrument_summary']
    assert 0 == len(actual['bjh'])
    assert 'hysteresis classification' not in actual['summary']['declined']
    from rouquerol import select_bet_range
    best = select_bet_range(source['ads'][:, 0], source['ads'][:, 1])['best']
    assert best.S_BET == pytest.approx(actual['summary']['S_BET'])


def test_smp_uses_correction_fields_instead_of_sample_constants(tmp_path):
    data, source = make_smp(coefficients=(.003, .08))
    np.testing.assert_allclose(source['ads'], read_bytes(tmp_path, data)['ads'], rtol=1e-12)


@pytest.mark.parametrize('measurement_id,tube_id', [(1, 'my'), (2, 'my'), (3, 'nz')])
def test_native_smp_accepts_measurement_and_tube_identifiers(tmp_path, measurement_id, tube_id):
    data, source = make_smp(
        measurement_id=measurement_id, prior_mode='zero', tube_id=tube_id,
    )
    actual = read_bytes(tmp_path, data)
    np.testing.assert_allclose(source['ads'], actual['ads'], rtol=1e-12)
    np.testing.assert_allclose(source['des'], actual['des'], rtol=1e-12)


@pytest.mark.parametrize('damage', ['version', 'truncated', 'directory', 'gas', 'mass', 'record', 'options', 'gas_area', 'nonfinite', 'p0', 'branch_count', 'overlap'])
def test_unsupported_or_corrupt_smp_is_rejected(tmp_path, damage):
    raw, _ = make_smp()
    data = bytearray(raw)
    if damage == 'version':
        data[data.index(b'SUBSET303') + 18] = 99
    elif damage == 'truncated':
        data = data[:-12]
    elif damage == 'directory':
        struct.pack_into('<I', data, 55, len(data) + 50)
    elif damage == 'gas':
        data = data.replace('N2\0'.encode('utf-16le'), 'Ar\0'.encode('utf-16le'))
    elif damage == 'mass':
        marker = b'\x01\x01\x00\x00\x00' + struct.pack('<d', .5)
        start = data.index(marker) + 5
        struct.pack_into('<d', data, start, 0.)
    elif damage == 'record':
        start = data.index(b'\xe0' + struct.pack('<d', float('nan')))
        data[start + 66 + 37] = 1
    elif damage == 'gas_area':
        start = data.index(struct.pack('<d', .162))
        struct.pack_into('<d', data, start, .18)
    elif damage == 'nonfinite':
        start = data.index(b'\xe0' + struct.pack('<d', float('nan')))
        struct.pack_into('<d', data, start + 66 + 27, float('nan'))
    elif damage == 'p0':
        start = data.index((b'\x01' + bytes(14)) * 3 + b'\x01')
        struct.pack_into('<d', data, start + 46 + 4 + 20, 700.)
    elif damage == 'branch_count':
        start = data.index(struct.pack('<Bddd', 7, 760., 760., 77.3))
        struct.pack_into('<I', data, start - 4, 1)
    elif damage == 'overlap':
        key, start, size = struct.unpack_from('<HII', data, 53)
        struct.pack_into('<HII', data, 63, key, start, size)
    else:
        start = data.index(b'\x01' + bytes(14) + b'\x07')
        data[start] = 2
    with pytest.raises(ValueError, match='SMP'):
        read_bytes(tmp_path, data)


def test_native_smp_upload_needs_no_companion(monkeypatch):
    from tests.test_asap_upload import upload_value, run_app
    data, _ = make_smp()
    def uploader(*args, **kwargs):
        assert 'smp_export' != kwargs.get('key')
        return [upload_value(data, 'native.SMP')]
    monkeypatch.setattr('streamlit.file_uploader', uploader)
    app = run_app()
    assert [] == [e.message for e in app.exception]
    assert 7 == len(app.tabs)
    assert any('直接读取' in e.value for e in app.success)
