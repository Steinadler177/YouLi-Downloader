"""外部工具管理：查询版本、自更新、缺失时从官方 Release 下载。

同一个类同时管理 yt-dlp（`-U`）和 BBDownT（`--update`）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .config import BIN_DIR, find_tool
from .process import ToolProcess, decode_output

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
BBDOWNT_URL = "https://github.com/LOVAHE/BBDownT/releases/latest/download/BBDownT_win-x64.exe"

_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")  # 去掉 BBDownT 的 "+<commit>" 后缀


def exe_mtime(path: str | None) -> float:
    if not path:
        return 0.0
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


class Updater(QObject):
    versionChanged = Signal(str)          # "" 表示未找到
    busyChanged = Signal(bool)
    statusChanged = Signal(str)           # 进度/结果文本
    finished = Signal(bool, str)
    versionCached = Signal(str, float)    # version, exe mtime — 供写入 config

    def __init__(self, parent: QObject | None = None, tool: str = "yt-dlp",
                 download_url: str = YTDLP_URL, update_args: tuple[str, ...] = ("-U",),
                 locate=None):
        super().__init__(parent)
        self.tool = tool
        self.locate = locate or (lambda: find_tool(tool))
        self.download_url = download_url
        self.update_args = list(update_args)
        self.version = ""
        self.busy = False
        self._proc: ToolProcess | None = None
        self._net = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

    def load_cache(self, version: str, mtime: float) -> bool:
        """若缓存命中（exe 仍在且 mtime 一致），立刻填版本，返回 True。"""
        exe = self.locate()
        if not exe or not version:
            return False
        if abs(exe_mtime(exe) - mtime) > 0.5:
            return False
        self._set_version(version)
        return True

    def check_version(self) -> None:
        exe = self.locate()
        if not exe:
            self._set_version("")
            self.versionCached.emit("", 0.0)
            return
        p = ToolProcess(exe, ["--version"], self, collect=True)
        p.exited.connect(lambda code, _err, p=p, exe=exe: self._on_version(p, code, exe))
        p.start()

    def _on_version(self, p: ToolProcess, code: int, exe: str) -> None:
        try:
            if code == 0:
                ver = self._parse_version(decode_output(p.stdout))
            else:
                ver = "?"
            self._set_version(ver)
            self.versionCached.emit(ver, exe_mtime(exe))
        finally:
            p.deleteLater()

    @staticmethod
    def _parse_version(text: str) -> str:
        first = text.strip().splitlines()[0] if text.strip() else ""
        m = _VERSION_RE.search(first)
        return m.group(0) if m else first

    def update(self) -> None:
        if self.busy:
            return
        exe = self.locate()
        if exe:
            self._run_self_update(exe)
        else:
            self._download()

    # ---- 自更新 ----
    def _run_self_update(self, exe: str) -> None:
        self._set_busy(True)
        self.statusChanged.emit(f"正在检查 {self.tool} 更新…")
        p = self._proc = ToolProcess(exe, self.update_args, self)
        lines: list[str] = []
        p.line.connect(lambda s: (lines.append(s), self.statusChanged.emit(s)))
        p.exited.connect(lambda code, err: self._done(code == 0, lines[-1] if lines and code == 0 else err))
        p.start()

    # ---- 首次下载 ----
    def _download(self) -> None:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        self._set_busy(True)
        self.statusChanged.emit(f"正在下载 {self.tool}.exe…")
        self._part = BIN_DIR / f"{self.tool}.exe.part"
        self._fh = open(self._part, "wb")
        req = QNetworkRequest(QUrl(self.download_url))
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.NoLessSafeRedirectPolicy)
        r = self._reply = self._net.get(req)
        r.readyRead.connect(lambda: self._fh.write(bytes(r.readAll())))
        r.downloadProgress.connect(self._on_dl_progress)
        r.finished.connect(self._on_dl_finished)

    def _on_dl_progress(self, got: int, total: int) -> None:
        if total > 0:
            self.statusChanged.emit(f"正在下载 {self.tool}.exe… {got * 100 // total}%")

    def _on_dl_finished(self) -> None:
        r, self._reply = self._reply, None
        self._fh.write(bytes(r.readAll()))
        self._fh.close()
        ok = r.error() == QNetworkReply.NoError and self._part.stat().st_size > 1_000_000
        if ok:
            os.replace(self._part, BIN_DIR / f"{self.tool}.exe")
            self._done(True, f"{self.tool}.exe 已下载到 bin/")
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
