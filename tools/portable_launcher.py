"""Windows 便携版入口；始终使用包内 Python 和资源。"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
from urllib.request import ProxyHandler, build_opener
import webbrowser

HOST = '127.0.0.1'
DEFAULT_PORT = 8501
PORT_ATTEMPTS = 100
READY_TIMEOUT = 60


def find_available_port(*, start=DEFAULT_PORT, attempts=PORT_ATTEMPTS):
    for port in range(start, min(start + attempts, 65536)):
        with socket.socket() as probe:
            try:
                probe.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError('没有可用的本地端口，请关闭不需要的服务后重试。')


def acquire_instance(path):
    import msvcrt
    handle = path.open('a+b')
    if path.stat().st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def open_when_ready(url, *, enabled=True):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            with opener.open(url + '/_stcore/health', timeout=1) as response:
                if response.status == 200:
                    if enabled:
                        webbrowser.open(url)
                    return True
        except OSError:
            pass
        time.sleep(0.25)
    print('网页尚未就绪，请检查窗口中的错误信息。', flush=True)
    return False


def reopen_existing(state, *, enabled):
    for _ in range(20):
        try:
            session = json.loads(state.read_text(encoding='utf-8'))
            url = f"http://{HOST}:{int(session['port'])}"
            print(f'本文件夹的程序已运行：{url}', flush=True)
            return 0 if open_when_ready(url, enabled=enabled) else 1
        except (OSError, ValueError, KeyError):
            time.sleep(0.25)
    raise RuntimeError('另一个启动窗口正在初始化，请稍后重试。')


def configure_environment(root):
    cache = root / '_runtime'
    cache.mkdir(exist_ok=True)
    os.environ['MPLBACKEND'] = 'Agg'
    os.environ['MPLCONFIGDIR'] = str(cache / 'matplotlib')
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    os.chdir(root / 'app')
    return cache


def serve(root, *, port, browser):
    from streamlit.web import cli
    url = f'http://{HOST}:{port}'
    print(f'BET 分析软件已开始启动。\n本机地址：{url}', flush=True)
    print('浏览器将自动打开；关闭此窗口或按 Ctrl+C 可停止程序。', flush=True)
    threading.Thread(target=open_when_ready, args=(url,),
                     kwargs={'enabled': browser}, daemon=True).start()
    sys.argv = ['streamlit', 'run', str(root / 'app' / 'portable_app.py'),
                '--server.address', HOST, '--server.port', str(port),
                '--server.headless', 'true', '--server.fileWatcherType', 'none',
                '--browser.gatherUsageStats', 'false',
                '--runner.fastReruns', 'false',
                '--global.developmentMode', 'false']
    cli.main()


def main():
    parser = argparse.ArgumentParser(description='BET 分析软件便携启动器')
    parser.add_argument('--no-browser', action='store_true', help='仅启动服务')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    cache = configure_environment(root)
    state = cache / 'session.json'
    lock = acquire_instance(cache / 'instance.lock')
    if lock is None:
        return reopen_existing(state, enabled=not args.no_browser)
    with lock:
        port = find_available_port()
        state.write_text(json.dumps({'port': port, 'pid': os.getpid()}), encoding='utf-8')
        serve(root, port=port, browser=not args.no_browser)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\n程序已停止。')
    except Exception:
        detail = traceback.format_exc()
        print(detail)
        error_path = Path(__file__).resolve().parent / '启动错误.log'
        error_path.write_text(detail, encoding='utf-8')
        print('启动失败，详细信息已写入“启动错误.log”。')
        raise SystemExit(1)
