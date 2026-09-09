"""便携启动器的端口避让、重复启动保护和模块完整性。"""
import importlib.util
from pathlib import Path
import socket

import pytest


ROOT = Path(__file__).resolve().parents[1]


def launcher():
    path = ROOT / 'tools' / 'portable_launcher.py'
    assert path.is_file(), '需要可移植的独立启动器'
    spec = importlib.util.spec_from_file_location('portable_launcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_skips_an_occupied_port():
    module = launcher()
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        port = occupied.getsockname()[1]
        selected = module.find_available_port(start=port)
        assert port != selected
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', selected))


def test_launcher_reports_exhausted_ports():
    module = launcher()
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        with pytest.raises(RuntimeError, match='端口'):
            module.find_available_port(start=occupied.getsockname()[1], attempts=1)


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows 便携包')
def test_instance_lock_prevents_duplicate_and_releases(tmp_path):
    module = launcher()
    path = tmp_path / '中文 路径.lock'
    first = module.acquire_instance(path)
    assert first is not None
    assert module.acquire_instance(path) is None
    first.close()
    again = module.acquire_instance(path)
    assert again is not None
    again.close()


def test_distribution_registers_native_reader_and_chinese_display():
    tomllib = pytest.importorskip('tomllib', reason='Windows 便携构建使用 Python 3.11+')
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    modules = config['tool']['setuptools']['py-modules']
    assert {'smp_reader', 'smp_binary', 'zh_cn'} <= set(modules)
