"""下载队列：排队、并发控制、取消/重试。只发信号，不关心界面。"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .command import DONE_TAG, ITEM_TAG, PROGRESS_TAG, download_args
from .config import Settings, find_tool
from .presets import get_preset
from .process import ToolProcess
from .progress import parse_progress

ACTIVE = ("queued", "downloading", "processing")


@dataclass
class _Task:
    id: int
    url: str
    preset: int
    title: str = ""
    status: str = "queued"
    job: ToolProcess | None = None


class DownloadManager(QObject):
    taskAdded = Signal(int, dict)
    taskChanged = Signal(int, dict)
    taskRemoved = Signal(int)
    runningChanged = Signal(int)

    def __init__(self, settings: Settings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self._tasks: dict[int, _Task] = {}
        self._ids = itertools.count(1)

    # ---- public API ----
    def add(self, url: str, preset: int, title: str = "") -> int:
        t = _Task(next(self._ids), url, preset, title)
        self._tasks[t.id] = t
        self.taskAdded.emit(t.id, {
            "taskId": t.id, "url": url, "title": title, "status": "queued",
            "progress": 0.0, "preset": get_preset(preset).name,
        })
        self.pump()
        return t.id

    def cancel(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if not t or t.status not in ACTIVE:
            return
        if t.job:
            t.job.cancel()  # 结束后在 _on_exit 中标记为 cancelled
        else:
            self._set(t, status="cancelled", message="已取消")

    def retry(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if t and t.status in ("error", "cancelled"):
            self._set(t, status="queued", progress=0.0, message="", speed="", eta="")
            self.pump()

    def remove(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if not t:
            return
        if t.status in ACTIVE:
            self.cancel(task_id)
        del self._tasks[task_id]
        self.taskRemoved.emit(task_id)

    def clear_finished(self) -> None:
        for t in [t for t in self._tasks.values() if t.status in ("done", "cancelled")]:
            self.remove(t.id)

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.job is not None)

    def shutdown(self) -> None:
        for t in self._tasks.values():
            if t.job:
                t.job.cancel()

    def pump(self) -> None:
        """在并发上限内启动排队中的任务。"""
        free = max(1, self.settings.max_concurrent) - self.running_count()
        for t in self._tasks.values():
            if free <= 0:
                break
            if t.status == "queued" and t.job is None:
                self._start(t)
                free -= 1

    # ---- internal ----
    def _set(self, t: _Task, **fields) -> None:
        if "status" in fields:
            t.status = fields["status"]
        if fields.get("title"):
            t.title = fields["title"]
        self.taskChanged.emit(t.id, fields)

    def _start(self, t: _Task) -> None:
        ytdlp = find_tool("yt-dlp")
        if not ytdlp:
            self._set(t, status="error", message="找不到 yt-dlp.exe，请在设置中下载")
            return
        args = download_args(t.url, get_preset(t.preset), self.settings, find_tool("ffmpeg"))
        job = t.job = ToolProcess(ytdlp, args, self)
        job.line.connect(lambda line, t=t: self._on_line(t, line))
        job.exited.connect(lambda code, err, t=t: self._on_exit(t, code, err))
        self._set(t, status="downloading", progress=-1.0, message="")
        job.start()
        self.runningChanged.emit(self.running_count())

    def _on_line(self, t: _Task, line: str) -> None:
        if line.startswith(PROGRESS_TAG):
            p = parse_progress(line[len(PROGRESS_TAG):])
            if not p:
                return
            state = p.pop("state")
            if state == "finished":
                # 一个流下载完：可能还有下一个流，或进入合并/转码
                self._set(t, status="processing", progress=1.0, speed="", eta="")
            else:
                self._set(t, status="downloading", **p)
        elif line.startswith(ITEM_TAG):
            idx, total, title = (line[len(ITEM_TAG):].split("|", 2) + ["", ""])[:3]
            item = f"{idx}/{total}" if idx and total else ""
            if item:  # 播放列表：保留列表标题，当前条目写进 message
                self._set(t, item=item, message=f"{item} · {title}", **({} if t.title else {"title": title}))
            else:
                self._set(t, title=title)
        elif line.startswith(DONE_TAG):
            self._set(t, filepath=line[len(DONE_TAG):].strip())

    def _on_exit(self, t: _Task, code: int, err: str) -> None:
        job, t.job = t.job, None
        if job:
            job.deleteLater()
        if t.id in self._tasks:
            if job and job.cancelled:
                self._set(t, status="cancelled", message="已取消", speed="", eta="")
            elif code == 0:
                self._set(t, status="done", progress=1.0, speed="", eta="", message="")
            else:
                self._set(t, status="error", message=err, speed="", eta="")
        self.runningChanged.emit(self.running_count())
        self.pump()
