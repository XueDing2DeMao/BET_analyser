"""在已经验证的 Windows x64 开发环境中构建自带依赖的便携目录。"""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import tomllib
from urllib.request import urlopen
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.11.9'
PYTHON_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
FONT_URL = 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf'
FONT_LICENSE_URL = 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE'
START_SCRIPT = r'''@echo off
setlocal
chcp 65001 >nul
title BET Analyser
cd /d "%~dp0"
if not exist "%~dp0runtime\python.exe" (
  echo Python runtime is missing. Extract the entire ZIP before starting.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" -I -X utf8 "%~dp0launcher.py" %*
if errorlevel 1 pause
'''


def fetch(url, target):
    if not target.exists():
        temporary = target.with_suffix(target.suffix + '.part')
        with urlopen(url, timeout=60) as source, temporary.open('wb') as dest:
            shutil.copyfileobj(source, dest)
        temporary.replace(target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def required_distributions(site_packages):
    installed = {canonicalize_name(d.metadata['Name']): d
                 for d in metadata.distributions(path=[str(site_packages)])}
    pending = [Requirement(line) for line in (REPO / 'requirements.txt').read_text().splitlines()
               if line.strip() and not line.startswith('#')]
    selected, visited = {}, set()
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        distribution = installed[name]
        if distribution.version not in requirement.specifier:
            raise ValueError(f'依赖版本不满足要求：{requirement}')
        selected[name] = distribution
        extras = {''} | set(requirement.extras)
        for extra in extras:
            if (name, extra) in visited:
                continue
            visited.add((name, extra))
            children = [Requirement(value) for value in distribution.requires or []]
            pending.extend(r for r in children if r.marker is None or r.marker.evaluate({'extra': extra}))
    return selected


def copy_distribution(distribution, destination):
    base = Path(distribution.locate_file('')).resolve()
    for relative in distribution.files or []:
        source = Path(distribution.locate_file(relative)).resolve()
        if not source.is_relative_to(base) or not source.is_file():
            continue
        if '__pycache__' in relative.parts or source.suffix in {'.pyc', '.pth'}:
            continue
        if source.name == 'direct_url.json':
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def add_runtime(output, cache):
    archive = cache / 'python-3.11.9-embed-amd64.zip'
    digest = fetch(PYTHON_URL, archive)
    runtime = output / 'runtime'
    if runtime.exists():
        raise FileExistsError('输出目录已包含运行时，请使用新的输出目录。')
    with zipfile.ZipFile(archive) as source:
        source.extractall(runtime)
    paths = 'python311.zip\n.\nLib/site-packages\n../app\nimport site\n'
    (runtime / 'python311._pth').write_text(paths, encoding='utf-8')
    packages = runtime / 'Lib' / 'site-packages'
    selected = required_distributions(Path(sys.prefix) / 'Lib' / 'site-packages')
    for name, distribution in sorted(selected.items()):
        print(f'收集 {name} {distribution.version}', flush=True)
        copy_distribution(distribution, packages)
    versions = {name: d.version for name, d in sorted(selected.items())}
    return {'python': PYTHON_VERSION, 'python_url': PYTHON_URL,
            'python_archive_sha256': digest, 'dependencies': versions}


def add_application(output):
    app = output / 'app'
    app.mkdir(exist_ok=True)
    config = tomllib.loads((REPO / 'pyproject.toml').read_text(encoding='utf-8'))
    for module in config['tool']['setuptools']['py-modules']:
        shutil.copy2(REPO / f'{module}.py', app)
    for name in ('LICENSE', 'README.md', 'SMP_FORMAT.md'):
        shutil.copy2(REPO / name, app)
    (app / '.streamlit').mkdir(exist_ok=True)
    shutil.copy2(REPO / '.streamlit' / 'config.toml', app / '.streamlit')
    shutil.copy2(REPO / 'tools' / 'portable_launcher.py', output / 'launcher.py')
    shutil.copy2(REPO / 'tools' / 'portable_app.py', app)
    (output / '启动 BET 分析软件.bat').write_text(START_SCRIPT, encoding='utf-8', newline='\r\n')


def add_font(output, cache):
    font = cache / 'NotoSansCJKsc-Regular.otf'
    digest = fetch(FONT_URL, font)
    license_file = cache / 'NotoSansCJK-LICENSE.txt'
    fetch(FONT_LICENSE_URL, license_file)
    fonts = output / 'runtime/Lib/site-packages/matplotlib/mpl-data/fonts/ttf'
    shutil.copy2(font, fonts)
    licenses = output / '许可证'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(license_file, licenses)
    shutil.copy2(output / 'runtime' / 'LICENSE.txt', licenses / 'Python-LICENSE.txt')
    shutil.copy2(REPO / 'LICENSE', licenses / 'BET-analyser-MIT.txt')
    return {'name': 'Noto Sans CJK SC Regular', 'url': FONT_URL, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'Windows' or platform.machine() != 'AMD64':
        raise RuntimeError('请在 Windows x64 中构建。')
    if platform.python_version() != PYTHON_VERSION:
        raise RuntimeError(f'请使用已验证的 Python {PYTHON_VERSION} 环境。')
    args.output.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    manifest = add_runtime(args.output, args.cache)
    add_application(args.output)
    manifest['font'] = add_font(args.output, args.cache)
    manifest['platform'] = 'Windows 10/11 x64'
    manifest['application'] = 'BET Analyser 3.0.0 中文版（SMP/XLS 适配）'
    (args.output / '依赖版本.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'已构建：{args.output}', flush=True)


if __name__ == '__main__':
    main()
