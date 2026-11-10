"""外部工具管理：查询 yt-dlp 版本、自更新（yt-dlp -U）、缺失时从官方 Release 下载。"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .config import BIN_DIR, find_tool
from .process import ToolProcess

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"


class Updater(QObject):
    versionChanged = Signal(str)          # "" 表示未找到
    busyChanged = Signal(bool)
    statusChanged = Signal(str)           # 进度/结果文本
    finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.version = ""
        self.busy = False
        self._proc: ToolProcess | None = None
        self._net = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

    def check_version(self) -> None:
        exe = find_tool("yt-dlp")
        if not exe:
            self._set_version("")
            return
        p = ToolProcess(exe, ["--version"], self, collect=True)
        p.exited.connect(lambda code, _err, p=p: (
            self._set_version(p.stdout.decode(errors="replace").strip() if code == 0 else "?"),
            p.deleteLater()))
        p.start()

    def update(self) -> None:
        if self.busy:
            return
        exe = find_tool("yt-dlp")
        if exe:
            self._run_self_update(exe)
        else:
            self._download()

    # ---- yt-dlp -U ----
    def _run_self_update(self, exe: str) -> None:
        self._set_busy(True)
        self.statusChanged.emit("正在检查更新…")
        p = self._proc = ToolProcess(exe, ["-U"], self)
        lines: list[str] = []
        p.line.connect(lambda s: (lines.append(s), self.statusChanged.emit(s)))
        p.exited.connect(lambda code, err: self._done(code == 0, lines[-1] if lines and code == 0 else err))
        p.start()

    # ---- 首次下载 ----
    def _download(self) -> None:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        self._set_busy(True)
        self.statusChanged.emit("正在下载 yt-dlp.exe…")
        self._part = BIN_DIR / "yt-dlp.exe.part"
        self._fh = open(self._part, "wb")
        req = QNetworkRequest(QUrl(YTDLP_URL))
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.NoLessSafeRedirectPolicy)
        r = self._reply = self._net.get(req)
        r.readyRead.connect(lambda: self._fh.write(bytes(r.readAll())))
        r.downloadProgress.connect(self._on_dl_progress)
        r.finished.connect(self._on_dl_finished)

    def _on_dl_progress(self, got: int, total: int) -> None:
        if total > 0:
            self.statusChanged.emit(f"正在下载 yt-dlp.exe… {got * 100 // total}%")

    def _on_dl_finished(self) -> None:
        r, self._reply = self._reply, None
        self._fh.write(bytes(r.readAll()))
        self._fh.close()
        ok = r.error() == QNetworkReply.NoError and self._part.stat().st_size > 1_000_000
        if ok:
            os.replace(self._part, BIN_DIR / "yt-dlp.exe")
            self._done(True, "yt-dlp.exe 已下载到 bin/")
        else:
            self._part.unlink(missing_ok=True)
            self._done(False, f"下载失败：{r.errorString()}")
        r.deleteLater()

    # ---- helpers ----
    def _done(self, ok: bool, msg: str) -> None:
        if self._proc:
            self._proc.deleteLater()
            self._proc = None
        self._set_busy(False)
        self.statusChanged.emit(msg)
        self.finished.emit(ok, msg)
        self.check_version()

    def _set_busy(self, v: bool) -> None:
        self.busy = v
        self.busyChanged.emit(v)

    def _set_version(self, v: str) -> None:
        self.version = v
        self.versionChanged.emit(v)
