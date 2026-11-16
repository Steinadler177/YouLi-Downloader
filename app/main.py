"""程序入口：高 DPI 设置、Material 风格、加载 QML。"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .bridge.backend import Backend
from .core.config import RES_DIR, Settings


def main() -> int:
    # 必须在创建 QGuiApplication 之前：125% / 150% 等缩放按真实比例渲染，不取整
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QQuickStyle.setStyle("Material")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("YouLi Downloader")
    app.setOrganizationName("YouLi")
    app.setWindowIcon(QIcon(str(RES_DIR / "ui" / "icons" / "app.svg")))

    backend = Backend(Settings.load())
    app.aboutToQuit.connect(backend.shutdown)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(RES_DIR / "ui" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    # 首帧出来后再查 yt-dlp/BBDownT 版本，避免与 Qt 加载抢磁盘
    QTimer.singleShot(0, backend.warmTools)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
