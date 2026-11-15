"""暴露给 QML 的唯一入口对象 `backend`。只做转接：调用 core，转发信号。"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from ..core import bili
from ..core.command import probe_args
from ..core.config import QUEUE_PATH, Settings, find_tool
from ..core.manager import DownloadManager
from ..core.presets import PRESETS
from ..core.process import ToolProcess, decode_output
from ..core.progress import summarize_info
from ..core.updater import BBDOWNT_URL, Updater
from ..models.task_model import TaskModel

# 批量粘贴时拆分链接：按空白/换行，保留 http(s) 与常见短链/B 站号
_URL_SPLIT = re.compile(r"[\s]+")
_LOOKS_LIKE_URL = re.compile(
    r"^(?:https?://\S+|www\.\S+|BV[0-9A-Za-z]{10}|av\d+|ep\d+|ss\d+)$",
    re.IGNORECASE,
)


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
    loginChanged = Signal()

    def __init__(self, settings: Settings, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        self._model = TaskModel(self)
        self._manager = DownloadManager(settings, self)
        self._manager.taskAdded.connect(self._model.add)
        self._manager.taskInserted.connect(self._model.insert)
        self._manager.taskChanged.connect(self._model.update)
        self._manager.taskRemoved.connect(self._model.remove)
        self._manager.taskChanged.connect(self._notify_task)
        self._manager.taskAdded.connect(lambda *_: self.queueChanged.emit())
        self._manager.taskInserted.connect(lambda *_: self.queueChanged.emit())
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

        self._bili_updater = Updater(self, tool=bili.TOOL, download_url=BBDOWNT_URL,
                                     update_args=("--update",), locate=bili.bbdownt_path)
        self._bili_status = ""
        self._bili_updater.versionChanged.connect(lambda _v: self.toolsChanged.emit())
        self._bili_updater.busyChanged.connect(lambda _b: self.toolsChanged.emit())
        self._bili_updater.statusChanged.connect(self._on_bili_status)
        self._bili_updater.finished.connect(lambda _ok, msg: (self.toast.emit(msg), self.loginChanged.emit()))
        self._bili_updater.check_version()

        self._login = bili.BiliLogin(self)
        self._login_qr = ""
        self._login_status = ""
        self._login.qrReady.connect(self._on_login_qr)
        self._login.status.connect(self._on_login_status)
        self._login.finished.connect(self._on_login_finished)

        self._probe_lines: list[str] | None = None
        self._probe: ToolProcess | None = None
        self._probe_info: dict = {}
        self._probe_url = ""

        self._restore_queue()

    # ---------------- 设置 ----------------
    outputDir = _setting("output_dir", str, settingsChanged)
    filenameTemplate = _setting("filename_template", str, settingsChanged)
    cookiesBrowser = _setting("cookies_browser", str, settingsChanged)
    downloadPlaylist = _setting("download_playlist", bool, settingsChanged)
    darkTheme = _setting("dark_theme", bool, settingsChanged)
    lastPreset = _setting("last_preset", int, settingsChanged)
    useBbdownt = _setting("use_bbdownt", bool, settingsChanged)
    biliApi = _setting("bili_api", str, settingsChanged)
    autoStartQueue = _setting("auto_start_queue", bool, settingsChanged)

    @Property(int, notify=settingsChanged)
    def windowX(self):
        return self._settings.window_x

    @Property(int, notify=settingsChanged)
    def windowY(self):
        return self._settings.window_y

    @Property(int, notify=settingsChanged)
    def windowW(self):
        return self._settings.window_w

    @Property(int, notify=settingsChanged)
    def windowH(self):
        return self._settings.window_h

    @Property(bool, notify=settingsChanged)
    def windowMaximized(self):
        return self._settings.window_maximized

    @Slot(int, int, int, int, bool)
    def saveWindowGeometry(self, x: int, y: int, w: int, h: int, maximized: bool):
        s = self._settings
        s.window_x, s.window_y = x, y
        s.window_w, s.window_h = max(w, 720), max(h, 520)
        s.window_maximized = maximized
        s.save()

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

    # ---------------- BBDownT / B 站 ----------------
    @Property(str, notify=toolsChanged)
    def bbdowntPath(self):
        return bili.bbdownt_path() or ""

    @Property(str, notify=toolsChanged)
    def bbdowntVersion(self):
        return self._bili_updater.version

    @Property(bool, notify=toolsChanged)
    def bbdowntUpdating(self):
        return self._bili_updater.busy

    @Property(str, notify=toolsChanged)
    def bbdowntStatus(self):
        return self._bili_status

    @Slot()
    def updateBbdownt(self):
        if self._manager.running_count():
            self.toast.emit("请等待当前任务结束后再更新 BBDownT")
            return
        self._manager.stop_bili_server()
        self._bili_updater.update()

    def _on_bili_status(self, s: str):
        self._bili_status = bili.strip_log(s)
        self.toolsChanged.emit()

    @Property(bool, notify=loginChanged)
    def biliLoggedIn(self):
        return bili.is_logged_in()

    @Property(bool, notify=loginChanged)
    def loginRunning(self):
        return self._login.running()

    @Property(str, notify=loginChanged)
    def loginQr(self):
        return self._login_qr

    @Property(str, notify=loginChanged)
    def loginStatus(self):
        return self._login_status

    @Slot()
    def biliLogin(self):
        if not bili.bbdownt_path():
            self.toast.emit("请先下载或放入 BBDownT.exe")
            return
        self._login_qr = ""
        self._login_status = ""
        self._login.start()
        self.loginChanged.emit()

    @Slot()
    def cancelBiliLogin(self):
        self._login.cancel()

    @Slot()
    def biliLogout(self):
        bili.logout()
        self._manager.stop_bili_server()
        self.toast.emit("已退出 B 站登录")
        self.loginChanged.emit()

    def _on_login_qr(self, path: str):
        self._login_qr = QUrl.fromLocalFile(path).toString()
        self.loginChanged.emit()

    def _on_login_status(self, s: str):
        self._login_status = s
        self.loginChanged.emit()

    def _on_login_finished(self, ok: bool, msg: str):
        self._login_qr = ""
        self._login_status = msg
        if ok:
            self._manager.stop_bili_server()
        self.toast.emit(msg)
        self.loginChanged.emit()

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
        # 多行时只解析第一行，便于预览
        urls = self.parseUrls(url)
        if urls:
            url = urls[0]
        if self._probe:
            self._probe.cancel()
        if self._manager.uses_bbdownt(url):
            exe = bili.bbdownt_path()
            lines: list[str] = []
            self._probe_lines = lines
            p = self._probe = ToolProcess(exe, bili.info_args(url, self._settings, find_tool("ffmpeg")),
                                          self, cwd=str(Path(exe).parent))
            p.line.connect(lines.append)
        else:
            ytdlp = find_tool("yt-dlp")
            if not ytdlp:
                self._probe = None
                self.toast.emit("找不到 yt-dlp.exe，请先在设置里下载")
                self.probeChanged.emit()
                return
            self._probe_lines = None
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
                if self._probe_lines is not None:
                    info = bili.parse_info(self._probe_lines, self._probe_url)
                else:
                    info = summarize_info(json.loads(decode_output(p.stdout)))
                info["url"] = self._probe_url
                self._probe_info = info
            except ValueError:
                self.toast.emit("解析失败：返回内容不是 JSON")
        elif not p.cancelled:
            self.toast.emit(f"解析失败：{bili.strip_log(err)}")
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

    @Property(bool, notify=queueChanged)
    def canStopQueue(self):
        return self._manager.can_stop()

    @Slot(str, result="QStringList")
    def parseUrls(self, text: str):
        """按空白拆分并去重，返回看起来像链接的条目。"""
        seen: set[str] = set()
        out: list[str] = []
        for part in _URL_SPLIT.split((text or "").strip()):
            u = part.strip().strip("<>\"'")
            if not u or not _LOOKS_LIKE_URL.match(u):
                continue
            if u.startswith("www."):
                u = "https://" + u
            key = u.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(u)
        return out

    @Slot(str, int)
    def addToQueue(self, text: str, preset: int):
        """回车 / 添加：支持多行批量入队。"""
        urls = self.parseUrls(text)
        if not urls:
            self.toast.emit("请先粘贴视频链接")
            return
        self.lastPreset = preset
        for url in urls:
            title = self._probe_info.get("title", "") if self._probe_info.get("url") == url else ""
            self._manager.add(url, preset, title)
        n = len(urls)
        self.toast.emit(f"已加入队列 {n} 个任务" if n > 1 else "已加入队列")
        if self._settings.auto_start_queue:
            self._manager.start_queue()

    @Slot()
    def startQueue(self):
        if not self._manager.start_queue():
            self.toast.emit("队列中没有待处理任务")
            return
        self.toast.emit("开始处理队列")

    @Slot()
    def stopQueue(self):
        if not self._manager.can_stop():
            self.toast.emit("当前没有运行中的队列")
            return
        self._manager.stop_queue()
        self.toast.emit("已停止队列")

    @Slot()
    def retryFailed(self):
        n = self._manager.retry_failed()
        if n == 0:
            self.toast.emit("没有失败任务可重试")
        else:
            self.toast.emit(f"已重试 {n} 个失败任务")

    @Slot(str, int)
    def download(self, url: str, preset: int):
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

    @Slot(str)
    def copyText(self, text: str):
        QGuiApplication.clipboard().setText(text or "")
        if text:
            self.toast.emit("已复制到剪贴板")

    @Slot(int)
    def copyTaskError(self, task_id: int):
        msg = self._model.get(task_id).get("message") or ""
        if not msg:
            self.toast.emit("没有可复制的错误信息")
            return
        self.copyText(msg)

    def _restore_queue(self) -> None:
        try:
            data = json.loads(QUEUE_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, list) and data:
            n = self._manager.restore(data)
            if n:
                self.toast.emit(f"已恢复 {n} 个未完成任务")

    def _save_queue(self) -> None:
        items = self._manager.export_incomplete()
        try:
            if items:
                QUEUE_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), "utf-8")
            elif QUEUE_PATH.exists():
                QUEUE_PATH.unlink()
        except OSError:
            pass

    def shutdown(self):
        if self._probe:
            self._probe.cancel()
        self._login.cancel()
        self._save_queue()
        self._manager.shutdown()

    def _notify_task(self, task_id: int, fields: dict):
        status = fields.get("status")
        if status == "done":
            title = self._model.get(task_id).get("title") or "任务"
            self.toast.emit(f"下载完成：{title}")
        elif status == "error":
            title = self._model.get(task_id).get("title") or "任务"
            self.toast.emit(f"下载失败：{title}")
