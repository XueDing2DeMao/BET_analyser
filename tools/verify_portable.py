"""使用包内解释器执行：检查路径隔离、实际样品、数值一致性和中文绘图。"""
import importlib
import json
import os
from pathlib import Path
import sys


def main():
    root = Path(sys.executable).resolve().parents[1]
    assert (root / 'launcher.py').is_file(), '必须使用便携包中的 Python'
    assert sys.flags.isolated and sys.flags.ignore_environment
    os.environ['MPLCONFIGDIR'] = str(root / '_runtime' / 'matplotlib')
    os.environ['MPLBACKEND'] = 'Agg'
    modules = ('numpy', 'scipy', 'pandas', 'matplotlib', 'xlrd', 'openpyxl',
               'streamlit', 'pyarrow', 'smp_reader', 'smp_binary', 'zh_cn')
    origins = {name: str(Path(importlib.import_module(name).__file__).resolve())
               for name in modules}
    assert all(Path(value).is_relative_to(root) for value in origins.values())
    assert all(Path(value).is_relative_to(root) for value in sys.path)
    results = compare_samples(root)
    print(json.dumps({'runtime': sys.executable, 'isolated': True,
                      'module_origins': origins, 'samples': results},
                     ensure_ascii=False, indent=2))


def compare_samples(root):
    import numpy as np
    from bet_analysis import read_bet_xls
    from rouquerol import select_bet_range
    from matplotlib import font_manager
    assert any(f.name == 'Noto Sans CJK SC' and Path(f.fname).is_relative_to(root)
               for f in font_manager.fontManager.ttflist)
    samples = {ext: read_bet_xls(str(root / '示例数据' / f'1-2002.{ext}'))
               for ext in ('SMP', 'XLS')}
    for branch, points in [('ads', 35), ('des', 28)]:
        actual, expected = samples['SMP'][branch], samples['XLS'][branch]
        assert points == len(actual) == len(expected)
        np.testing.assert_allclose(expected[:, 0], actual[:, 0], rtol=1e-14, atol=0)
        np.testing.assert_allclose(expected[:, 1], actual[:, 1], rtol=2e-6)
    results = {}
    for ext, data in samples.items():
        best = select_bet_range(data['ads'][:, 0], data['ads'][:, 1])['best']
        assert best.valid and abs(best.S_BET - 28.5452) < 0.0001
        results[ext] = {'ads': len(data['ads']), 'des': len(data['des']),
                        'BET': best.S_BET, 'C': best.C, 'points': best.n_points,
                        'R2': best.R2, 'valid': bool(best.valid)}
    return results


if __name__ == '__main__':
    main()
