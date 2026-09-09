"""ASAP 2460 v3.01 SMP 原生读取（受限格式，已用成对 XLS 验证）。

基础气体校正见厂家 Calculations - 2460 ASAP, Dec 2024, pp. 43–45。
子集布局及两项附加校正字段来自二进制对照，非厂家公开格式规范。
未知版本/配置一律拒绝，不能把总投气量直接视为单位质量吸附量。
"""
import io
import struct
import numpy as np
from smp_binary import (
    Reader, require, sections, sample_metadata, measurement_header,
    measurement_points, saturation_table,
)

STANDARD_PRESSURE_MMHG = 760.
TUBE_PROFILE_SIZE = 202
TUBE_ALPHA_OFFSET = 139
# 仅允许已核验的样品管/线性状态方程/无热迁移校正配置。
# alpha 的 8 字节清零后比较，避免固化样品测量数值。
TUBE_PROFILE = bytes.fromhex(
    '0100000000000000f03f00000000000002000000000000f03f000000000000f03f'
    '000000000000f03f000000000000f03f000000000000f03f000000000000f03f'
    '000000000000f03f000000000000f03f000000000000f03f000000000000f03f'
    '000000000000f03f000000000000f03f000000000000f03f0100000000000000f03f'
    '000000000000f03f000000000000000000000100000000000000000000000000000000'
    '00c087400000000001000100690076000000000000000000000000000000000000000000'
)


def _gas(payload):
    from bet_analysis import N2_STP_TO_LIQUID
    reader = Reader(payload)
    reader.expect(b'\x0f')
    description, gas = reader.string(), reader.string()
    require(gas == 'N2', f'当前分析仅支持氮气 N₂，文件气体为 {gas!r}')
    reader.expect(bytes(2))
    reader.take(8)
    reader.expect(bytes(2))
    alpha, liquid_factor, diameter, area = reader.unpack('dddd')
    require(area == .162 and abs(liquid_factor - N2_STP_TO_LIQUID) < 1e-9, '氮气物性参数不同于项目计算常数')
    return description, alpha


def _temperatures(reader):
    reader.expect(b'\x05')
    reader.take(7)  # 包含未初始化保留字节。
    ambient, = reader.unpack('d')
    reader.expect(b'\x02')
    count, = reader.unpack('I')
    reader.take(count * 16)  # 气体饱和蒸气压-温度参考表。
    reader.expect(b'\x01' + bytes(14) + b'\x07')
    entered_cold, entered_warm, alpha, cold, warm = reader.unpack('ddddd')
    require(np.isfinite([ambient, alpha, cold, warm]).all(), '自由空间参数无效')
    require(0 < warm < cold and 0 <= alpha < .001, '自由空间或非理想气体参数不支持')
    return ambient, alpha, cold, warm


def _corrections(reader, alpha):
    reader.expect(b'\x05')
    reader.string()
    tube = bytearray(reader.take(TUBE_PROFILE_SIZE))
    tube_alpha, = struct.unpack_from('<d', tube, TUBE_ALPHA_OFFSET)
    tube[TUBE_ALPHA_OFFSET:TUBE_ALPHA_OFFSET + 8] = bytes(8)
    require(tube == TUBE_PROFILE and tube_alpha == alpha, '样品管或气体校正配置尚不支持')
    reader.expect(b'\x01\x00')
    offset_fraction, gradient_fraction = reader.unpack('dd')
    require(np.isfinite([offset_fraction, gradient_fraction]).all(), '自由空间校正系数无效')
    require(0 <= offset_fraction < .1 and 0 <= gradient_fraction < 1, '自由空间校正系数越界')
    return offset_fraction, gradient_fraction


def _conditions(reader, points, times):
    reader.expect(struct.pack('<I', 1))
    n_ads, = reader.unpack('I')
    reader.expect(b'\x07')
    standard, entered_p0, bath = reader.unpack('ddd')
    require(standard == STANDARD_PRESSURE_MMHG, '标准压力单位尚不支持')
    saturation_table(reader, points, times)
    ambient, alpha, cold, warm = _temperatures(reader)
    require(np.isfinite(bath) and 70 <= bath <= 85 and ambient > bath, '氮气分析温度不支持')
    offsets = _corrections(reader, alpha)
    return dict(n_ads=n_ads, bath=bath, ambient=ambient, alpha=alpha,
                cold=cold, warm=warm, corrections=offsets)


def _isotherm(points, conditions, mass):
    c = conditions
    bath_volume = (c['cold'] - c['warm']) / (1 - c['bath'] / c['ambient'])
    offset, gradient = c['corrections']
    # 读取文件内的校正系数，不能将样例系数或 XLS 回归值硬编码在此。
    effective_cold = c['cold'] - offset * bath_volume
    require(np.isfinite(bath_volume) and effective_cold > 0, '校正后的自由空间无效')
    pressure = points[:, 0]
    free_gas = pressure / STANDARD_PRESSURE_MMHG * (
        effective_cold + pressure * c['alpha'] * bath_volume * (1 - gradient))
    uptake = (points[:, 2] - free_gas) / mass
    require(np.isfinite(uptake).all() and (uptake > 0).all(), '校正后吸附量无效')
    isotherm = np.column_stack((points[:, 1], uptake))
    n_ads = c['n_ads']
    require(5 <= n_ads <= len(points), '吸附支点数无效')
    ads = isotherm[:n_ads]
    des = isotherm[n_ads-1:] if n_ads < len(points) else np.empty((0, 2))
    require(np.all(np.diff(ads[:, 0]) > 0), '吸附支压力不是严格递增')
    require(np.all(np.diff(des[:, 0]) < 0), '脱附支压力不是严格递减')
    return ads, des


def inspect_smp(data):
    """返回从 SMP 本身读取的元数据和两条等温线，不读取任何配套文件。"""
    blocks = sections(data)
    name, mass = sample_metadata(blocks[301])
    gas, alpha = _gas(blocks[337])
    reader = Reader(blocks[303])
    version, serial = measurement_header(reader)
    points, times = measurement_points(reader)
    conditions = _conditions(reader, points, times)
    require(alpha == conditions['alpha'], '报告与测量的气体校正参数不一致')
    ads, des = _isotherm(points, conditions, mass)
    return dict(name=name, mass=mass, gas=gas, version=version, serial=serial,
                ads=ads, des=des, conditions=conditions)


def _select_summary(result):
    from rouquerol import select_bet_range
    ads, summary = result['ads'], result['summary']
    best = select_bet_range(ads[:, 0], ads[:, 1])['best']
    if best is not None and best.valid:
        summary.update(Vm=best.Vm, S_BET=best.S_BET, C=best.C,
                       start_pt=best.i0, end_pt=best.i1,
                       window_method='Rouquerol')


def read_smp(data):
    """适配既有分析入口，优先采用满足 Rouquerol 判据的 BET 区间。"""
    from bet_analysis import _read_csv_isotherm
    parsed = inspect_smp(data)
    csv = io.StringIO()
    np.savetxt(csv, parsed['ads'], delimiter=',', comments='',
               header='relative pressure,quantity adsorbed (cm3/g STP)')
    csv.seek(0)
    result = _read_csv_isotherm(csv)
    # pandas 的文本浮点读取可能改变末位；分析数组保持 SMP double 原值。
    result['ads'] = parsed['ads']
    result['des'] = parsed['des']
    p, q = parsed['ads'][parsed['ads'][:, 0] < 1].T
    result['bet_pts'] = np.column_stack((p, p / (q * (1 - p))))
    summary = result['summary']
    summary['source_format'] = 'SMP'
    summary['declined'] = {
        '仪器 BJH 分布表': 'SMP 原始等温线不含已计算的 BJH 表，尚未解码仪器报告选项',
        '仪器汇总对照': '结果由本项目重新计算，不是仪器导出报告值',
    }
    if not len(parsed['des']):
        summary['declined']['滞后环分类'] = 'SMP 仅包含吸附支'
    _select_summary(result)
    return result
