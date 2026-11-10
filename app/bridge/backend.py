"""暴露给 QML 的唯一入口对象 `backend`。只做转接：调用 core，转发信号。"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from ..core.command import probe_args
from ..core.config import Settings, find_tool
from ..core.manager import DownloadManager
from ..core.presets import PRESETS
from ..core.process import ToolProcess, decode_output
from ..core.progress import summarize_info
from ..core.updater import Updater
from ..models.task_model import TaskModel


def _setting(name: str, typ, notify):
    """把 Settings 的字段包装成 QML 可读写、自动保存的属性。"""
    def fget(self):
        return getattr(self._settings, name)

    def fset(self, value):
        if getattr(self._settings, name) == value:
            return
        setattr(self._settings, name, value)
        self._settings.save()
        self.settingsChanged.emit()

    return Property(typ, fget, fset, notify=notify)


class Backend(QObject):
    toast = Signal(str)
    settingsChanged = Signal()
    toolsChanged = Signal()
    probeChanged = Signal()
    queueChanged = Signal()

    def __init__(self, settings: Settings, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        self._model = TaskModel(self)
        self._manager = DownloadManager(settings, self)
        self._manager.taskAdded.connect(self._model.add)
        self._manager.taskChanged.connect(self._model.update)
        self._manager.taskRemoved.connect(self._model.remove)
        self._manager.taskChanged.connect(self._notify_task)
        self._manager.taskAdded.connect(lambda *_: self.queueChanged.emit())
        self._manager.taskChanged.connect(lambda *_: self.queueChanged.emit())
        self._manager.taskRemoved.connect(lambda *_: self.queueChanged.emit())
        self._manager.runningChanged.connect(lambda _r: self.queueChanged.emit())
        self._manager.workStatusChanged.connect(lambda _s: self.queueChanged.emit())

        self._updater = Updater(self)
        self._update_status = ""
        self._updater.versionChanged.connect(lambda _v: self.toolsChanged.emit())
        self._updater.busyChanged.connect(lambda _b: self.toolsChanged.emit())
        self._updater.statusChanged.connect(self._on_update_status)
        self._updater.finished.connect(lambda _ok, msg: self.toast.emit(msg))
        self._updater.check_version()

        self._probe: ToolProcess | None = None
        self._probe_info: dict = {}
        self._probe_url = ""

    # ---------------- 设置 ----------------
    outputDir = _setting("output_dir", str, settingsChanged)
    filenameTemplate = _setting("filename_template", str, settingsChanged)
    cookiesBrowser = _setting("cookies_browser", str, settingsChanged)
    maxConcurrent = _setting("max_concurrent", int, settingsChanged)
    downloadPlaylist = _setting("download_playlist", bool, settingsChanged)
    darkTheme = _setting("dark_theme", bool, settingsChanged)
    lastPreset = _setting("last_preset", int, settingsChanged)

    @Slot(QUrl)
    def setOutputDirUrl(self, url: QUrl):
        path = url.toLocalFile()
        if path:
            self.outputDir = str(Path(path))

    @Slot(result=QUrl)
    def outputDirUrl(self):
        return QUrl.fromLocalFile(self._settings.output_dir)

    @Slot()
    def openOutputDir(self):
        Path(self._settings.output_dir).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._settings.output_dir))

    # ---------------- 外部工具 ----------------
    @Property(str, notify=toolsChanged)
    def ytdlpVersion(self):
        return self._updater.version

    @Property(str, notify=toolsChanged)
    def ytdlpPath(self):
        return find_tool("yt-dlp") or ""

    @Property(str, notify=toolsChanged)
    def ffmpegPath(self):
        return find_tool("ffmpeg") or ""

    @Property(bool, notify=toolsChanged)
    def updating(self):
        return self._updater.busy

    @Property(str, notify=toolsChanged)
    def updateStatus(self):
        return self._update_status

    @Slot()
    def updateYtdlp(self):
        if self._manager.running_count():
            self.toast.emit("请等待当前下载完成后再更新 yt-dlp")
            return
        self._updater.update()

    def _on_update_status(self, s: str):
        self._update_status = s
        self.toolsChanged.emit()

    # ---------------- 解析链接（顶部预览，可选） ----------------
    @Property(bool, notify=probeChanged)
    def probing(self):
        return self._probe is not None

    @Property("QVariantMap", notify=probeChanged)
    def probeInfo(self):
        return self._probe_info

    @Slot(str)
    def probe(self, url: str):
        url = url.strip()
        if not url:
            return
        ytdlp = find_tool("yt-dlp")
        if not ytdlp:
            self.toast.emit("找不到 yt-dlp.exe，请先在设置里下载")
            return
        if self._probe:
            self._probe.cancel()
        p = self._probe = ToolProcess(ytdlp, probe_args(url, self._settings), self, collect=True)
        self._probe_url = url
        self._probe_info = {}
        p.exited.connect(lambda code, err, p=p: self._on_probe_done(p, code, err))
        p.start()
        self.probeChanged.emit()

    @Slot()
    def clearProbe(self):
        if self._probe:
            self._probe.cancel()
        self._probe_info = {}
        self.probeChanged.emit()

    def _on_probe_done(self, p: ToolProcess, code: int, err: str):
        p.deleteLater()
        if p is not self._probe:
            return
        self._probe = None
        if code == 0:
            try:
                info = summarize_info(json.loads(decode_output(p.stdout)))
                info["url"] = self._probe_url
                self._probe_info = info
            except ValueError:
                self.toast.emit("解析失败：返回内容不是 JSON")
        elif not p.cancelled:
            self.toast.emit(f"解析失败：{err}")
        self.probeChanged.emit()

    # ---------------- 下载队列 ----------------
    @Property(QObject, constant=True)
    def tasks(self):
        return self._model

    @Property("QVariantList", constant=True)
    def presetNames(self):
        return [p.name for p in PRESETS]

    @Property(bool, notify=queueChanged)
    def queueRunning(self):
        return self._manager.is_queue_running()

    @Property(bool, notify=queueChanged)
    def hasPending(self):
        return self._manager.has_pending()

    @Property(int, notify=queueChanged)
    def failedCount(self):
        return self._manager.failed_count()

    @Property(str, notify=queueChanged)
    def workStatus(self):
        return self._manager.work_status()

    @Slot(str, int)
    def addToQueue(self, url: str, preset: int):
        """回车 / 添加：只入队，不立刻下载。"""
        url = url.strip()
        if not url:
            self.toast.emit("请先粘贴视频链接")
            return
        title = self._probe_info.get("title", "") if self._probe_info.get("url") == url else ""
        self.lastPreset = preset
        self._manager.add(url, preset, title)
        self.toast.emit("已加入队列")

    @Slot()
    def startQueue(self):
        if not self._manager.start_queue():
            self.toast.emit("队列中没有待处理任务")
            return
        self.toast.emit("开始处理队列")

    @Slot()
    def stopQueue(self):
        self._manager.stop_queue()
        self.toast.emit("已停止接新任务")

    @Slot()
    def retryFailed(self):
        n = self._manager.retry_failed()
        if n == 0:
            self.toast.emit("没有失败任务可重试")
        else:
            self.toast.emit(f"已重试 {n} 个失败任务")

    @Slot(str, int)
    def download(self, url: str, preset: int):
        """兼容旧调用：等同于加入队列。"""
        self.addToQueue(url, preset)

    @Slot(int)
    def cancel(self, task_id: int):
        self._manager.cancel(task_id)

    @Slot(int)
    def retry(self, task_id: int):
        self._manager.retry(task_id)

    @Slot(int)
    def remove(self, task_id: int):
        self._manager.remove(task_id)

    @Slot()
    def clearFinished(self):
        self._manager.clear_finished()

    @Slot(int)
    def openFile(self, task_id: int):
        path = self._model.get(task_id).get("filepath")
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            self.openOutputDir()

    @Slot(int)
    def showInFolder(self, task_id: int):
        path = self._model.get(task_id).get("filepath")
        if path and os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            self.openOutputDir()

    @Slot(result=str)
    def clipboardText(self):
        return QGuiApplication.clipboard().text().strip()

    def shutdown(self):
        if self._probe:
            self._probe.cancel()
        self._manager.shutdown()

    def _notify_task(self, task_id: int, fields: dict):
        status = fields.get("status")
        if status == "done":
            title = self._model.get(task_id).get("title") or "任务"
            self.toast.emit(f"下载完成：{title}")
        elif status == "error":
            title = self._model.get(task_id).get("title") or "任务"
            self.toast.emit(f"下载失败：{title}")
