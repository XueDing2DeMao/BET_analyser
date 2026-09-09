# Windows 便携版构建

使用已经通过回归验证的 Windows x64、Python 3.11.9 环境。
构建脚本读取当前环境中 requirements.txt 的递归运行依赖，复制包文件和许可信息；不包含开发虚拟环境、可编辑安装链接、私密配置或 pip。

```powershell
.venv\Scripts\python.exe -X utf8 tools\build_portable.py --output ..\发布包\新便携目录 --cache ..\.bet-runtime\portable-cache
```

输出目录必须尚未包含 runtime。首次构建从 Python 官方下载嵌入式运行时，从 Noto 官方仓库获取中文字体及许可，下载文件与 SHA-256 记录在缓存和构建清单中。构建需要网络，成品使用不需要网络安装依赖。

将说明书及配图放入“使用说明”，将用户授权的样品放入“示例数据”；通过网页实际验证并将导出样例放入“示例结果”。2026-09-09 的完整交付件保存在工作区父目录“发布包”中。

```powershell
新便携目录\runtime\python.exe -I -X utf8 tools\verify_portable.py
.venv\Scripts\python.exe -X utf8 tools\archive_portable.py --source ..\发布包\新便携目录 --output ..\发布包\新便携包.zip
```

封装只收集显式列出的程序、运行时、说明和样例目录，排除运行缓存、日志和 secrets.toml，输出逐文件校验清单及 ZIP 校验值。发布前必须在不同的中文／空格路径重新解压，用包内解释器和启动脚本验证。

启动器只绑定 127.0.0.1，自动避让占用端口；使用 Windows 文件锁避免同一文件夹重复启动。便携入口用进程内共享锁串行执行各浏览器会话的分析，并关闭快速并行重跑，保护 Matplotlib 的全局绘图状态。服务在启动窗口中运行，关闭窗口或 Ctrl+C 停止服务；仅关闭浏览器不会退出服务。

运行中生成的字体缓存、端口和文件锁位于 `_runtime`，不打入 ZIP。支持的 SMP 版本及校正配置见项目 `SMP_FORMAT.md`。打包不会扩大解析器的格式支持范围。
