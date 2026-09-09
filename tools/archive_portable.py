"""封装便携目录并生成 SHA-256；排除运行缓存和日志。"""
import argparse
import hashlib
from pathlib import Path
import zipfile

FOLDERS = {'app', 'runtime', '许可证', '使用说明', '示例数据', '示例结果'}
FILES = {'launcher.py', '启动 BET 分析软件.bat', '先读我.txt', '依赖版本.json'}
CHECKSUM_FILE = '文件校验.sha256'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def selected_files(root):
    selected = []
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if not file.is_file() or '__pycache__' in relative.parts:
            continue
        if file.suffix in {'.pyc', '.log'} or file.name == 'secrets.toml':
            continue
        if relative.parts[0] in FOLDERS or relative.as_posix() in FILES:
            selected.append(file)
    return selected


def archive(root, target):
    required = ['runtime/python.exe', 'app/app_bet.py', 'app/portable_app.py', '启动 BET 分析软件.bat',
                '使用说明/用户使用说明书.md', '使用说明/用户使用说明书.html',
                '示例数据/1-2002.SMP', '示例数据/1-2002.XLS']
    for name in required:
        if not (root / name).is_file():
            raise FileNotFoundError(name)
    selected = selected_files(root)
    checksums = '\n'.join(f'{digest(f)}  {f.relative_to(root).as_posix()}' for f in selected)
    (root / CHECKSUM_FILE).write_text(checksums + '\n', encoding='utf-8')
    selected.append(root / CHECKSUM_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for file in selected:
            package.write(file, f'{root.name}/{file.relative_to(root).as_posix()}')
    checksum = digest(target)
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {target.name}\n', encoding='utf-8')
    print(f'ZIP：{target}\n大小：{target.stat().st_size / 1024**2:.1f} MiB')
    print(f'文件数：{len(selected)}\nSHA256：{checksum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    archive(args.source.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
