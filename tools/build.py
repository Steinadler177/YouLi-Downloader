"""打包成 Windows 程序（PyInstaller，单文件夹模式）。

用法：双击 build.bat，或  .venv\\Scripts\\python.exe tools\\build.py
必须在只装了 PySide6-Essentials 的环境（build.bat 创建的 .venv-build）里打包：
开发用的 .venv 是完整 PySide6，会把约 200 MB 的 Qt6WebEngineCore.dll 一起打进去。
输出：dist\\YTBDownloader\\YTBDownloader.exe，旁边是可单独更新的 bin\\ 目录。

为什么用单文件夹（--onedir）而不是单文件（--onefile）：
- 启动快（单文件每次都要先解压到临时目录）；
- bin\\ 里的 yt-dlp / BBDownT / ffmpeg 需要放在 exe 旁边，并且能被程序自更新。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "YTBDownloader"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_OUT = DIST / NAME

# 程序没用到、但体积很大的 Qt 模块，排除掉
EXCLUDE_QT = [
    "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel", "QtWebSockets",
    "QtPdf", "QtPdfWidgets", "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DLogic", "Qt3DAnimation",
    "Qt3DExtras", "QtCharts", "QtDataVisualization", "QtGraphs", "QtMultimedia", "QtMultimediaWidgets",
    "QtSpatialAudio", "QtQuick3D", "QtBluetooth", "QtNfc", "QtPositioning", "QtLocation",
    "QtSensors", "QtSerialPort", "QtSerialBus", "QtSql", "QtTest", "QtDesigner", "QtHelp",
    "QtRemoteObjects", "QtScxml", "QtStateMachine", "QtTextToSpeech", "QtHttpServer",
    "QtWidgets", "QtOpenGLWidgets", "QtPrintSupport", "QtUiTools", "QtXml",
]
# bin\\ 里只复制这些工具，绝不复制 BBDownT.data（登录 Cookie）等运行时文件
TOOL_GLOBS = ["yt-dlp.exe", "BBDownT.exe", "BBDownT_win-x64.exe", "ffmpeg.exe", "ffprobe.exe", "README.txt"]
# QML 里没用到的大模块（PyInstaller 会把整个 qml 目录带上）
PRUNE_QML = ["QtWebEngine", "QtQuick3D", "Qt3D", "QtCharts", "QtGraphs", "QtDataVisualization",
             "QtMultimedia", "QtLocation", "QtPositioning", "QtSensors", "QtWebView", "QtWebChannel",
             "QtWebSockets", "QtTest", "QtScxml", "QtRemoteObjects", "QtTextToSpeech", "QtPdf"]


def make_icon() -> Path:
    """把 app.svg 渲染成多尺寸 .ico。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(["build"])
    renderer = QSvgRenderer(str(ROOT / "app" / "ui" / "icons" / "app.svg"))
    BUILD.mkdir(exist_ok=True)
    img = QImage(256, 256, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()
    ico = BUILD / "app.ico"
    if not img.save(str(ico)):
        raise SystemExit("生成图标失败")
    del app
    return ico


def run_pyinstaller(icon: Path) -> None:
    import PyInstaller.__main__

    args = [
        str(ROOT / "run.pyw"),
        "--name", NAME,
        "--onedir", "--windowed", "--noconfirm", "--clean",
        "--icon", str(icon),
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        # RES_DIR 在打包后是 _internal/app，QML 和图标要放到这里
        "--add-data", f"{ROOT / 'app' / 'ui'};app/ui",
    ]
    for mod in EXCLUDE_QT:
        args += ["--exclude-module", f"PySide6.{mod}"]
    PyInstaller.__main__.run(args)


# 只用 Material 风格（Basic 是它的后备风格，必须保留），其余控件风格删掉
UNUSED_STYLES = ["Fusion", "Imagine", "Universal", "FluentWinUI3", "Windows"]


def _remove(path: Path) -> int:
    if path.is_dir():
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        shutil.rmtree(path, ignore_errors=True)
        return size
    if path.is_file():
        size = path.stat().st_size
        path.unlink()
        return size
    return 0


def prune() -> int:
    """删除没用到的 QML 模块、控件风格、软件 OpenGL 和非中文翻译，返回删掉的字节数。"""
    qt = APP_OUT / "_internal" / "PySide6"
    qml = qt / "qml"
    freed = 0
    for name in PRUNE_QML:
        for d in qml.glob(name + "*"):
            freed += _remove(d)
    for style in UNUSED_STYLES:
        freed += _remove(qml / "QtQuick" / "Controls" / style)
        for dll in qt.glob(f"Qt6QuickControls2{style}*.dll"):
            freed += _remove(dll)
    # Qt Quick 在 Windows 上默认用 Direct3D 11，不需要 20 MB 的软件 OpenGL 后备
    freed += _remove(qt / "opengl32sw.dll")
    for f in (qt / "translations").glob("*.qm"):
        if "zh_CN" not in f.name:
            freed += _remove(f)
    return freed


def copy_tools() -> list[str]:
    src, dst = ROOT / "bin", APP_OUT / "bin"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in TOOL_GLOBS:
        f = src / name
        if f.is_file():
            shutil.copy2(f, dst / name)
            copied.append(name)
    return copied


def folder_size(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 / 1024


def main() -> None:
    import importlib.util
    if importlib.util.find_spec("PySide6.QtWebEngineCore"):
        print("警告：当前环境装了完整 PySide6（含 WebEngine），打包会多出约 200 MB。"
              "请用 build.bat（只含 PySide6-Essentials 的 .venv-build）打包。")
    print("==> 生成图标")
    icon = make_icon()
    print("==> 运行 PyInstaller")
    run_pyinstaller(icon)
    print("==> 精简未使用的 Qt 文件")
    freed = prune()
    print(f"    删除 {freed / 1024 / 1024:.1f} MB")
    print("==> 复制 bin\\ 外部工具")
    tools = copy_tools()
    print("    " + (", ".join(tools) if tools else "（bin\\ 里没有工具，首次运行时在设置里下载）"))
    app_size = folder_size(APP_OUT) - folder_size(APP_OUT / "bin")
    print(f"\n完成：{APP_OUT / (NAME + '.exe')}")
    print(f"程序本体 {app_size:.0f} MB，外部工具 {folder_size(APP_OUT / 'bin'):.0f} MB")
    print("整个 dist\\YTBDownloader 文件夹可以直接复制到别的电脑使用。")


if __name__ == "__main__":
    sys.exit(main())
