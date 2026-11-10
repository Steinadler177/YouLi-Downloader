"""下载队列：添加、顺序分析/下载、失败重试。只发信号，不关心界面。"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from . import bili
from .command import DONE_TAG, ITEM_TAG, PROGRESS_TAG, download_args, probe_args
from .config import Settings, find_tool
from .presets import get_preset
from .process import ToolProcess, decode_output
from .progress import parse_progress, summarize_info

# 队列生命周期状态（界面文案在 StatusChip）
STATUS_ADDED = "added"
STATUS_ANALYZING = "analyzing"
STATUS_ANALYZED = "analyzed"
STATUS_DOWNLOADING = "downloading"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"

BUSY = (STATUS_ANALYZING, STATUS_DOWNLOADING, STATUS_PROCESSING)
RETRYABLE = (STATUS_ERROR, STATUS_CANCELLED)
# 开始队列时会处理的待办状态
PENDING = (STATUS_ADDED, STATUS_ANALYZED)


@dataclass
class _Task:
    id: int
    url: str
    preset: int
    title: str = ""
    status: str = STATUS_ADDED
    params: str = ""
    job: ToolProcess | None = None
    extra: dict = field(default_factory=dict)


def _title_ok(title: str) -> bool:
    """过滤解码失败产生的替换字符，避免用乱码覆盖已有标题。"""
    return bool(title) and "\ufffd" not in title


class DownloadManager(QObject):
    taskAdded = Signal(int, dict)
    taskChanged = Signal(int, dict)
    taskRemoved = Signal(int)
    runningChanged = Signal(bool)
    workStatusChanged = Signal(str)

    def __init__(self, settings: Settings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self._tasks: dict[int, _Task] = {}
        self._order: list[int] = []
        self._ids = itertools.count(1)
        self._queue_running = False
        self._work_status = "空闲"
        self._active_id: int | None = None
        self._bili = bili.BiliServer(self)

    def uses_bbdownt(self, url: str) -> bool:
        """B 站链接且有 BBDownT 时走 BBDownT，否则回退 yt-dlp。"""
        return self.settings.use_bbdownt and bili.is_bilibili(url) and bool(bili.bbdownt_path())

    # ---- public API ----
    def add(self, url: str, preset: int, title: str = "") -> int:
        """追加到队尾，状态=已添加；不自动开始。"""
        preset_obj = get_preset(preset)
        if self.uses_bbdownt(url):
            opts = " ".join(f"{k}={v}" for k, v in preset_obj.bili.items())
            params = f"BBDownT {opts}".strip()
        else:
            params = " ".join(preset_obj.args)
        t = _Task(next(self._ids), url, preset, title, params=params)
        self._tasks[t.id] = t
        self._order.append(t.id)
        self.taskAdded.emit(t.id, {
            "taskId": t.id,
            "url": url,
            "title": title or url,
            "status": STATUS_ADDED,
            "progress": 0.0,
            "preset": preset_obj.name,
            "params": t.params,
            "message": "",
        })
        # 队列已在跑时，新任务会在当前忙完后由 pump 接上
        if self._queue_running:
            self.pump()
        return t.id

    def start_queue(self) -> bool:
        """开始/继续依次处理队列中的待办任务。"""
        if not any(self._tasks[i].status in PENDING for i in self._order if i in self._tasks):
            return False
        self._queue_running = True
        self.runningChanged.emit(True)
        self.pump()
        return True

    def stop_queue(self) -> None:
        """停止队列：不再接后续任务，并取消当前正在分析/下载的任务。"""
        was_running = self._queue_running or self.running_count() > 0
        self._queue_running = False
        # 取消当前忙碌任务
        active = self._tasks.get(self._active_id) if self._active_id else None
        if active and active.status in BUSY and active.job:
            active.job.cancel()
        else:
            for t in self._tasks.values():
                if t.status in BUSY and t.job:
                    t.job.cancel()
                    break
        if was_running:
            self.runningChanged.emit(False)
            self._set_work("已停止队列")

    def can_stop(self) -> bool:
        return self._queue_running or self.running_count() > 0

    def retry_failed(self) -> int:
        """把失败/取消的任务重置为已添加，并启动队列。"""
        n = 0
        for tid in self._order:
            t = self._tasks.get(tid)
            if t and t.status in RETRYABLE:
                self._set(t, status=STATUS_ADDED, progress=0.0, message="",
                          speed="", eta="", size="")
                n += 1
        if n:
            self._queue_running = True
            self.runningChanged.emit(True)
            self.pump()
        return n

    def cancel(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if not t or t.status not in BUSY:
            return
        if t.job:
            t.job.cancel()
        else:
            self._set(t, status=STATUS_CANCELLED, message="已取消")
            self.pump()

    def retry(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if t and t.status in RETRYABLE:
            self._set(t, status=STATUS_ADDED, progress=0.0, message="",
                      speed="", eta="", size="")
            if self._queue_running:
                self.pump()

    def remove(self, task_id: int) -> None:
        t = self._tasks.get(task_id)
        if not t:
            return
        if t.status in BUSY:
            self.cancel(task_id)
            if t.job:
                # 等退出回调里再删，避免竞态；这里先标移除意图
                t.extra["remove_after"] = True
                return
        self._order = [i for i in self._order if i != task_id]
        del self._tasks[task_id]
        self.taskRemoved.emit(task_id)

    def clear_finished(self) -> None:
        for tid in [i for i in self._order
                    if self._tasks.get(i) and self._tasks[i].status in (STATUS_DONE, STATUS_CANCELLED)]:
            self.remove(tid)

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.job is not None)

    def is_queue_running(self) -> bool:
        return self._queue_running

    def work_status(self) -> str:
        return self._work_status

    def has_pending(self) -> bool:
        return any(self._tasks[i].status in PENDING for i in self._order if i in self._tasks)

    def failed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status in RETRYABLE)

    def stop_bili_server(self) -> None:
        self._bili.stop()

    def shutdown(self) -> None:
        self._queue_running = False
        for t in self._tasks.values():
            if t.job:
                t.job.cancel()
        self._bili.stop()
        self._set_work("空闲")

    def pump(self) -> None:
        """队列运行中时，同一时刻只推进一个任务：先分析再下载。"""
        if not self._queue_running:
            if self.running_count() == 0:
                self._set_work("空闲")
            return
        if self.running_count() > 0:
            return
        for tid in self._order:
            t = self._tasks.get(tid)
            if not t:
                continue
            if t.status == STATUS_ADDED:
                self._start_analyze(t)
                return
            if t.status == STATUS_ANALYZED:
                self._start_download(t)
                return
        # 没有待办了
        self._queue_running = False
        self.runningChanged.emit(False)
        self._set_work("队列已完成")

    # ---- internal ----
    def _set_work(self, text: str) -> None:
        if self._work_status == text:
            return
        self._work_status = text
        self.workStatusChanged.emit(text)

    def _label(self, t: _Task) -> str:
        return t.title if _title_ok(t.title) and t.title != t.url else t.url

    def _set(self, t: _Task, **fields) -> None:
        if "status" in fields:
            t.status = fields["status"]
        if fields.get("title"):
            t.title = fields["title"]
        self.taskChanged.emit(t.id, fields)
        self._refresh_work(t, fields)

    def _refresh_work(self, t: _Task, fields: dict) -> None:
        if self._active_id not in (None, t.id):
            return
        status = fields.get("status", t.status)
        name = self._label(t)
        if status == STATUS_ANALYZING:
            self._set_work(f"正在分析：{name}")
        elif status == STATUS_DOWNLOADING:
            prog = fields.get("progress", -1.0)
            speed = fields.get("speed", "")
            extra = []
            if isinstance(prog, (int, float)) and prog >= 0:
                extra.append(f"{round(prog * 100)}%")
            size = fields.get("size", "")
            if size:
                extra.append(size)
            if speed:
                extra.append(speed)
            suffix = ("  ·  " + "  ".join(extra)) if extra else ""
            self._set_work(f"正在下载：{name}{suffix}")
        elif status == STATUS_PROCESSING:
            self._set_work(f"正在处理：{name}（合并/转码）")
        elif status == STATUS_ERROR:
            self._set_work(f"失败：{name} — {fields.get('message') or t.extra.get('last_err', '')}")
        elif status in (STATUS_DONE, STATUS_ANALYZED, STATUS_CANCELLED) and not self._queue_running:
            if status == STATUS_DONE:
                self._set_work(f"下载完成：{name}")
            elif not self.has_pending() and self.running_count() == 0:
                self._set_work("空闲")

    def _start_analyze(self, t: _Task) -> None:
        if self.uses_bbdownt(t.url):
            self._start_bili_analyze(t)
            return
        t.extra.pop("bili_lines", None)
        ytdlp = find_tool("yt-dlp")
        if not ytdlp:
            self._set(t, status=STATUS_ERROR, message="找不到 yt-dlp.exe，请在设置中下载")
            self.pump()
            return
        self._active_id = t.id
        job = t.job = ToolProcess(ytdlp, probe_args(t.url, self.settings), self, collect=True)
        job.exited.connect(lambda code, err, t=t: self._on_analyze_exit(t, code, err))
        self._set(t, status=STATUS_ANALYZING, message="正在分析…")
        job.start()

    def _on_analyze_exit(self, t: _Task, code: int, err: str) -> None:
        job, t.job = t.job, None
        remove_after = bool(t.extra.pop("remove_after", False))
        if job:
            job.deleteLater()
        if t.id not in self._tasks:
            self._active_id = None
            self.pump()
            return
        if job and job.cancelled:
            self._set(t, status=STATUS_CANCELLED, message="已取消")
        elif code == 0:
            try:
                lines = t.extra.pop("bili_lines", None)
                info = (bili.parse_info(lines) if lines is not None
                        else summarize_info(json.loads(decode_output(job.stdout))))
                title = info.get("title") or t.title or t.url
                if not _title_ok(title):
                    title = t.title or t.url
                self._set(t, status=STATUS_ANALYZED, title=title, message="分析完成")
            except ValueError:
                self._set(t, status=STATUS_ERROR, message="分析失败：返回内容不是 JSON")
        else:
            self._set(t, status=STATUS_ERROR, message=err or "分析失败")
        self._active_id = None
        if remove_after:
            self.remove(t.id)
        self.pump()

    def _start_bili_analyze(self, t: _Task) -> None:
        exe = bili.bbdownt_path()
        self._active_id = t.id
        lines: list[str] = []
        t.extra["bili_lines"] = lines
        job = t.job = ToolProcess(exe, bili.info_args(t.url, self.settings, find_tool("ffmpeg")),
                                  self, cwd=str(Path(exe).parent))
        job.line.connect(lines.append)
        job.exited.connect(lambda code, err, t=t: self._on_analyze_exit(t, code, bili.strip_log(err)))
        self._set(t, status=STATUS_ANALYZING, message="BBDownT 分析中…")
        job.start()

    def _start_bili_download(self, t: _Task) -> None:
        self._active_id = t.id
        job = t.job = bili.BiliJob(self._bili, t.url, get_preset(t.preset), self.settings, self)
        job.update.connect(lambda fields, t=t: self._on_bili_update(t, dict(fields)))
        job.exited.connect(lambda code, err, t=t: self._on_download_exit(t, code, err))
        self._set(t, status=STATUS_DOWNLOADING, progress=-1.0, message="")
        job.start()

    def _on_bili_update(self, t: _Task, fields: dict) -> None:
        state = fields.pop("state", None)
        if "title" in fields:
            fields.update(self._pick_title(t, fields.pop("title")))
        if state == "processing":
            fields["status"] = STATUS_PROCESSING
        elif state == "downloading":
            fields["status"] = STATUS_DOWNLOADING
        if fields:
            self._set(t, **fields)

    def _start_download(self, t: _Task) -> None:
        if self.uses_bbdownt(t.url):
            self._start_bili_download(t)
            return
        ytdlp = find_tool("yt-dlp")
        if not ytdlp:
            self._set(t, status=STATUS_ERROR, message="找不到 yt-dlp.exe，请在设置中下载")
            self.pump()
            return
        self._active_id = t.id
        args = download_args(t.url, get_preset(t.preset), self.settings, find_tool("ffmpeg"))
        job = t.job = ToolProcess(ytdlp, args, self)
        job.line.connect(lambda line, t=t: self._on_line(t, line))
        job.exited.connect(lambda code, err, t=t: self._on_download_exit(t, code, err))
        self._set(t, status=STATUS_DOWNLOADING, progress=-1.0, message="")
        job.start()

    def _pick_title(self, t: _Task, title: str) -> dict:
        if not _title_ok(title):
            return {}
        if t.title and t.title != t.url and _title_ok(t.title):
            return {}
        return {"title": title}

    def _on_line(self, t: _Task, line: str) -> None:
        if line.startswith(PROGRESS_TAG):
            p = parse_progress(line[len(PROGRESS_TAG):])
            if not p:
                return
            state = p.pop("state")
            if state == "finished":
                self._set(t, status=STATUS_PROCESSING, progress=1.0, speed="", eta="")
            else:
                self._set(t, status=STATUS_DOWNLOADING, **p)
        elif line.startswith(ITEM_TAG):
            idx, total, title = (line[len(ITEM_TAG):].split("|", 2) + ["", ""])[:3]
            item = f"{idx}/{total}" if idx and total else ""
            title_fields = self._pick_title(t, title)
            if item:
                msg_title = title if _title_ok(title) else (t.title or "")
                self._set(t, item=item, message=f"{item} · {msg_title}", **title_fields)
            elif title_fields:
                self._set(t, **title_fields)
        elif line.startswith(DONE_TAG):
            self._set(t, filepath=line[len(DONE_TAG):].strip())

    def _on_download_exit(self, t: _Task, code: int, err: str) -> None:
        job, t.job = t.job, None
        remove_after = bool(t.extra.pop("remove_after", False))
        if job:
            job.deleteLater()
        if t.id in self._tasks:
            if job and job.cancelled:
                self._set(t, status=STATUS_CANCELLED, message="已取消", speed="", eta="")
            elif code == 0:
                self._set(t, status=STATUS_DONE, progress=1.0, speed="", eta="", message="")
            else:
                self._set(t, status=STATUS_ERROR, message=err, speed="", eta="")
        self._active_id = None
        if remove_after and t.id in self._tasks:
            self.remove(t.id)
        self.pump()
