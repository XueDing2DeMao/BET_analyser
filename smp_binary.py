"""有边界检查的 Micromeritics SMP 容器读取，不扫描浮点数猜测字段。"""
import struct
import numpy as np

SIGNATURE = b'^vMIC##&&FS\x00'
SECTION_HEADER_SIZE = 18
RECORD_SIZE = 66
RECORD_PREFIX = b'\xe0' + struct.pack('<d', float('nan')) + b'\x05\x00'
POINT_OPTIONS = (b'\x01' + bytes(14)) * 3 + b'\x01'


def require(condition, message):
    if not condition:
        raise ValueError(f'SMP {message}；请使用该样品导出的 XLS/XLSX。')


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, count):
        require(0 <= count <= len(self.data) - self.pos, '文件被截断或字段长度无效')
        start = self.pos
        self.pos += count
        return self.data[start:self.pos]

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))

    def expect(self, value):
        require(self.take(len(value)) == value, '版本、布局或校正选项尚不支持')

    def string(self):
        self.expect(b'\xe0\x01\x00')
        size, = self.unpack('I')
        require(size % 2 == 0, '文本字段长度无效')
        raw = self.take(size)
        require(not raw or raw.endswith(b'\0\0'), '文本字段不完整')
        try:
            return raw.decode('utf-16le').rstrip('\0')
        except UnicodeDecodeError as exc:
            raise ValueError('SMP 文本编码无效；请使用 XLS/XLSX。') from exc


def _section(data, key, *, offset, size):
    require(0 <= offset <= len(data) - SECTION_HEADER_SIZE, '目录地址越界')
    reader = Reader(data[offset:])
    reader.expect(f'SUBSET{key}'.encode().ljust(10, b'\0'))
    reader.take(2)  # 内部保留字段可能含未初始化字节。
    stored_key, stored_size = reader.unpack('HI')
    require((key, size) == (stored_key, stored_size), '目录与数据块不一致')
    return reader.take(size)


def sections(data):
    reader = Reader(data)
    reader.expect(SIGNATURE + b'0200')
    reader.take(8)  # 创建/修改时间。
    offset, size = reader.unpack('II')
    require(offset >= 32, '目录与文件头重叠')
    index = Reader(_section(data, 101, offset=offset, size=size))
    index.expect(b'\x02')
    count, = index.unpack('H')
    entries = [index.unpack('HII') for _ in range(count)]
    blocks, occupied = {}, [(0, offset + SECTION_HEADER_SIZE + size)]
    for key, start, length in entries:
        require(key not in blocks, '目录包含重复数据块')
        blocks[key] = _section(data, key, offset=start, size=length)
        occupied.append((start, start + SECTION_HEADER_SIZE + length))
    occupied.sort()
    require(all(a[1] <= b[0] for a, b in zip(occupied, occupied[1:])), '数据块重叠')
    require({301, 303, 337} <= blocks.keys(), '缺少样品、测量或气体数据块')
    return blocks


def sample_metadata(payload):
    reader = Reader(payload)
    reader.expect(b'\x13\x00\x00')
    name = reader.string()
    for _ in range(3):
        reader.string()
    reader.take(6)
    for _ in range(5):
        reader.string()
    reader.expect(b'\x01\x01\x00\x00\x00')
    mass, = reader.unpack('d')
    require(np.isfinite(mass) and mass > 0, '样品质量必须为正数')
    return name, mass


def measurement_header(reader):
    reader.expect(b'\x0d\xe0\x03\x00\x09\x01\x00')
    measurement_id, = reader.unpack('H')
    require(measurement_id > 0, '测量序号无效')
    versions = [reader.string(), reader.string()]
    require(versions == ['ASAP 2460 Version 3.01'] * 2, '仅验证了 ASAP 2460 Version 3.01')
    serial = reader.string()
    reader.take(64)  # 两组仪器日期以及保留字段。
    reader.expect(b'\x03\x07')
    return versions[0], serial


def measurement_points(reader):
    count, = reader.unpack('I')
    require(5 <= count <= (len(reader.data) - reader.pos) // RECORD_SIZE - 1, '测量点数无效')
    rows, times, relatives, priors = [], [], [], []
    for i in range(count + 1):
        reader.expect(RECORD_PREFIX)
        pressure, relative, dose, minutes = reader.unpack('dddH')
        reader.expect(bytes(3))
        prior, = reader.unpack('d')
        reader.expect(bytes(16) + b'\x05\x00')
        relatives.append(relative)
        priors.append(prior)
        if i == 0:
            require((pressure, relative, dose, minutes) == (0., 0., 0., 0), '初始记录不支持')
            continue
        rows.append((pressure, relative, dose))
        times.append(minutes)
    chained = np.array_equal(priors, [0., *relatives[:-1]])
    unchained = not any(priors)
    require(chained or unchained, '测量记录链不连续')
    points = np.array(rows)
    require(np.isfinite(points).all(), '测量数据包含非有限数值')
    require((points[:, :2] > 0).all() and (points[:, 1] <= 1).all(), '压力超出物理范围')
    require(np.all(np.diff(times) >= 0), '测量时间顺序无效')
    return points, np.array(times)


def saturation_table(reader, points, times):
    reader.expect(POINT_OPTIONS)
    count, = reader.unpack('I')
    require(len(points) <= count <= (len(reader.data) - reader.pos) // 10 - 1, '饱和蒸气压记录数无效')
    reader.expect(bytes(10))
    table = np.array([reader.unpack('dH') for _ in range(count)])
    require(np.isfinite(table).all() and (table[:, 0] > 0).all(), '饱和蒸气压无效')
    require(count == len(points) + 1, '尚不支持间隔测量的饱和蒸气压')
    require(np.array_equal(table[1:, 1], times), '饱和蒸气压与测量点时间不匹配')
    require(np.allclose(points[:, 0] / table[1:, 0], points[:, 1], rtol=1e-10), '相对压力与饱和蒸气压不一致')
