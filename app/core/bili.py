"""BBDownT 后端：B 站链接的分析、下载与扫码登录。

为什么用 `BBDownT serve` 而不是直接调命令行：
BBDownT 检测到输出被重定向（Console.IsOutputRedirected）时完全不打印进度，
只有服务器模式的任务会上报进度。所以下载走本机 HTTP API：
    POST /add-task          -> {"TaskId": "..."}
    GET  /get-tasks/{id}    -> Progress / DownloadSpeed / SavePaths / Error ...
分析（标题等）仍用一次性的 `BBDownT <url> -info` 命令行，它会打印 "视频标题: ..."。

限制：服务器无法取消单个任务，取消 = 结束服务进程（队列一次只跑一个任务，不影响其他任务），
下一个任务会自动重新拉起服务。
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import tempfile
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .config import BIN_DIR, Settings, find_tool
from .presets import Preset
from .process import ToolProcess
from .progress import human_size

TOOL = "BBDownT"

_BILI_RE = re.compile(
    r"(?:^|//)(?:[\w-]+\.)*(?:bilibili\.com|b23\.tv|bili2233\.cn)(?:/|$)"
    r"|^(?:BV[0-9A-Za-z]{10}|av\d+|ep\d+|ss\d+)$",
    re.IGNORECASE,
)
_LOG_PREFIX = re.compile(r"^\[\d{4}-\d{2}-\d{2} [\d:.]+\]\s*-\s*")
_MEDIA_EXT = (".mp4", ".mkv", ".flv", ".m4a", ".flac", ".mp3", ".aac", ".eac3", ".mp4a")
_AUDIO_EXT = (".m4a", ".flac", ".aac", ".mp3", ".eac3")


def is_bilibili(url: str) -> bool:
    return bool(_BILI_RE.search(url.strip()))


def bbdownt_path() -> str | None:
    """bin/BBDownT.exe 优先；也接受 Release 原始文件名 BBDownT_win-x64.exe。"""
    found = find_tool(TOOL)
    if found:
        return found
    raw = BIN_DIR / "BBDownT_win-x64.exe"
    return str(raw) if raw.is_file() else None


def strip_log(line: str) -> str:
    """去掉 BBDownT 日志行的 "[时间] - " 前缀。"""
    return _LOG_PREFIX.sub("", line).strip()


# ---------------- 分析（命令行 -info） ----------------
def _api_flags(settings: Settings) -> list[str]:
    return {"tv": ["-tv"], "app": ["-app"]}.get(settings.bili_api, [])


def page_selection(url: str, settings: Settings) -> str:
    """BBDownT 默认下载所有分P。未开启“下载整个播放列表”时只取一个分P：
    链接里带 ?p=N 时交给 BBDownT 自动选该集（返回空），否则选 P1。"""
    if settings.download_playlist:
        return "ALL"
    if re.search(r"[?&]p=\d+", url) or re.search(r"/(ep|ss)\d+", url, re.I):
        return ""
    return "1"


def info_args(url: str, settings: Settings, ffmpeg: str | None) -> list[str]:
    # -hs：不打印每条音视频流；-p 1：只解析一个分P，减少请求（降低触发风控的概率）
    args = [url.strip(), "-info", "-hs", "-p", "1", *_api_flags(settings)]
    if ffmpeg:
        args += ["--ffmpeg-path", ffmpeg]
    return args


def parse_info(lines: list[str]) -> dict:
    """从 -info 输出里取标题和分 P 数，返回与 summarize_info 相同结构的字典。"""
    title, pages, listed = "", 0, 0
    for raw in lines:
        line = strip_log(raw)
        if line.startswith("视频标题:"):
            title = line.split(":", 1)[1].strip()
        elif m := re.match(r"^共计\s*(\d+)\s*个分P", line):
            pages = int(m.group(1))
        elif re.match(r"^P\d+\s*[:：]", line):
            listed += 1  # 分P列表可能被 "......" 截断，仅在没有“共计”行时使用
    pages = pages or listed
    return {
        "title": title, "uploader": "", "duration": "", "thumbnail": "",
        "isPlaylist": pages > 1, "count": max(pages, 1), "heights": "",
    }


# ---------------- 服务进程 ----------------
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class BiliServer(QObject):
    """按需启动/复用一个本机 `BBDownT serve` 进程。"""

    stopped = Signal(str)   # 服务进程退出（原因）

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.net = QNetworkAccessManager(self)
        self._proc: ToolProcess | None = None
        self._port = 0
        self._ready = False
        self._waiters: list[tuple] = []
        self._log: deque[str] = deque(maxlen=20)
        self._probe_timer = QTimer(self, interval=300)
        self._probe_timer.timeout.connect(self._health_check)
        self._probe_tries = 0

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    def ensure(self, on_ready, on_fail) -> None:
        if self._ready and self._proc and self._proc.is_running():
            on_ready()
            return
        self._waiters.append((on_ready, on_fail))
        if self._proc is None:
            self._launch()

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        self._ready = False
        self._probe_timer.stop()
        if proc:
            proc.cancel()

    # ---- HTTP helpers ----
    def request(self, method: str, path: str, body: dict | None, callback) -> None:
        """callback(status_code, parsed_json_or_None, error_text)"""
        req = QNetworkRequest(QUrl(self.base + path))
        req.setTransferTimeout(10_000)
        if body is not None:
            req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            reply = self.net.post(req, json.dumps(body, ensure_ascii=False).encode("utf-8"))
        elif method == "DELETE":
            reply = self.net.deleteResource(req)
        else:
            reply = self.net.get(req)

        def done():
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) or 0
            raw = bytes(reply.readAll())
            data = None
            if raw:
                try:
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                except ValueError:
                    data = raw.decode("utf-8", errors="replace")
            err = "" if reply.error() == QNetworkReply.NoError else reply.errorString()
            reply.deleteLater()
            callback(int(status), data, err)

        reply.finished.connect(done)

    # ---- internal ----
    def _launch(self) -> None:
        exe = bbdownt_path()
        if not exe:
            self._fail_all("找不到 BBDownT.exe，请放到 bin/ 或在设置中下载")
            return
        self._port = _free_port()
        self._log.clear()
        args = ["serve", "-l", self.base, "--server-allow-custom-output"]
        # 服务器任务不允许指定 FFmpegPath，只会在 PATH / 程序目录里找 ffmpeg，
        # 所以把我们找到的 ffmpeg 所在目录加到服务进程的 PATH 前面
        ffmpeg = find_tool("ffmpeg")
        p = self._proc = ToolProcess(exe, args, self, cwd=str(Path(exe).parent),
                                     path_prepend=str(Path(ffmpeg).parent) if ffmpeg else None)
        p.line.connect(lambda s: self._log.append(strip_log(s)))
        p.exited.connect(lambda code, err, p=p: self._on_exit(p, err))
        p.start()
        self._probe_tries = 0
        self._probe_timer.start()

    def _health_check(self) -> None:
        self._probe_tries += 1
        if self._probe_tries > 60:  # ~18 秒
            self._probe_timer.stop()
            self.stop()
            self._fail_all("BBDownT 服务启动超时")
            return
        self.request("GET", "/get-tasks/", None, self._on_health)

    def _on_health(self, status: int, _data, _err: str) -> None:
        if status == 200 and not self._ready and self._proc:
            self._ready = True
            self._probe_timer.stop()
            waiters, self._waiters = self._waiters, []
            for ok, _fail in waiters:
                ok()

    def _on_exit(self, p: ToolProcess, err: str) -> None:
        p.deleteLater()
        if p is not self._proc:
            return  # 主动 stop() 的旧进程
        self._proc = None
        self._ready = False
        self._probe_timer.stop()
        reason = "BBDownT 服务意外退出" + (f"：{self._log[-1]}" if self._log else f"（{err}）")
        self._fail_all(reason)
        self.stopped.emit(reason)

    def _fail_all(self, msg: str) -> None:
        waiters, self._waiters = self._waiters, []
        for _ok, fail in waiters:
            fail(msg)


# ---------------- 单个下载任务 ----------------
class BiliJob(QObject):
    """接口与 manager 中 yt-dlp 任务对齐：update(dict) 发进度，exited(code, err) 结束。"""

    update = Signal(dict)
    exited = Signal(int, str)

    POLL_MS = 700

    def __init__(self, server: BiliServer, url: str, preset: Preset, settings: Settings,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.server = server
        self.url = url.strip()
        self.preset = preset
        self.settings = settings
        self.cancelled = False
        self._finished = False
        self._task_id = ""
        self._misses = 0
        self._convert: ToolProcess | None = None
        self._timer = QTimer(self, interval=self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        server.stopped.connect(self._on_server_stopped)

    def start(self) -> None:
        self.server.ensure(self._submit, lambda msg: self._finish(1, msg))

    def cancel(self) -> None:
        if self._finished:
            return
        self.cancelled = True
        self._timer.stop()
        if self._convert:
            self._convert.cancel()
        # 服务器不支持取消单个任务：结束服务进程即可停止当前下载
        self.server.stop()
        QTimer.singleShot(0, lambda: self._finish(-1, "已取消"))

    # ---- internal ----
    def _options(self) -> dict:
        opts = {"Url": self.url, "WorkDir": self.settings.output_dir, **self.preset.bili}
        if self.settings.bili_api == "tv":
            opts["UseTvApi"] = True
        elif self.settings.bili_api == "app":
            opts["UseAppApi"] = True
        pages = page_selection(self.url, self.settings)
        if pages:
            opts["SelectPage"] = pages
        return opts  # 注意：服务器拒绝 FFmpegPath 等路径选项（HTTP 400），ffmpeg 通过 PATH 提供

    def _submit(self) -> None:
        if self.cancelled:
            return
        Path(self.settings.output_dir).mkdir(parents=True, exist_ok=True)
        self.server.request("POST", "/add-task", self._options(), self._on_submitted)

    def _on_submitted(self, status: int, data, err: str) -> None:
        if self.cancelled:
            return
        if status == 202 and isinstance(data, dict) and data.get("TaskId"):
            self._task_id = str(data["TaskId"])
            self.update.emit({"state": "downloading", "progress": -1.0, "message": "BBDownT 解析中…"})
            self._timer.start()
        else:
            detail = data if isinstance(data, str) and data else err
            self._finish(1, f"提交任务失败（HTTP {status}）：{detail}")

    def _poll(self) -> None:
        self.server.request("GET", f"/get-tasks/{self._task_id}", None, self._on_task)

    def _on_task(self, status: int, data, err: str) -> None:
        if self.cancelled or self._finished:
            return
        if status != 200 or not isinstance(data, dict):
            self._misses += 1
            if self._misses > 15:
                self._finish(1, f"无法获取任务状态：{err or status}")
            return
        self._misses = 0
        title = data.get("Title") or ""
        if data.get("TaskFinishTime"):
            self._timer.stop()
            if data.get("IsSuccessful"):
                # SavePaths 是相对 WorkDir（保存目录）的路径
                base = Path(self.settings.output_dir)
                paths = [str(p if (p := Path(raw)).is_absolute() else base / p)
                         for raw in data.get("SavePaths") or []]
                self._on_success(paths, title)
            else:
                self._finish(1, data.get("Error") or "BBDownT 下载失败")
            return
        progress = float(data.get("Progress") or 0.0)
        speed = data.get("DownloadSpeed") or 0
        done = data.get("TotalDownloadedBytes") or 0
        fields = {
            "state": "processing" if progress >= 0.999 else "downloading",
            "progress": progress if progress > 0 else -1.0,
            "speed": f"{human_size(speed)}/s" if speed else "",
            "size": human_size(done),
            "message": "",
        }
        if title:
            fields["title"] = title
        self.update.emit(fields)

    def _on_success(self, paths: list[str], title: str) -> None:
        media = [p for p in paths if p.lower().endswith(_MEDIA_EXT) and Path(p).exists()]
        main = media[0] if media else (paths[0] if paths else "")
        fields = {"filepath": main}
        if title:
            fields["title"] = title
        self.update.emit(fields)
        target = self.preset.audio_format
        if target and main.lower().endswith(_AUDIO_EXT) and not main.lower().endswith("." + target):
            self._convert_audio(main, target)
        else:
            self._finish(0, "")

    def _convert_audio(self, src: str, fmt: str) -> None:
        ffmpeg = find_tool("ffmpeg")
        if not ffmpeg:
            self._finish(1, f"已下载 {Path(src).name}，但找不到 ffmpeg，无法转为 {fmt.upper()}")
            return
        dst = str(Path(src).with_suffix("." + fmt))
        codec = ["-c:a", "libmp3lame", "-q:a", "0"] if fmt == "mp3" else []
        self.update.emit({"state": "processing", "progress": 1.0, "message": f"转换为 {fmt.upper()}…"})
        p = self._convert = ToolProcess(ffmpeg, ["-y", "-hide_banner", "-loglevel", "error",
                                                 "-i", src, "-vn", *codec, dst], self)

        def done(code: int, err: str):
            self._convert = None
            p.deleteLater()
            if self.cancelled:
                return
            if code == 0:
                Path(src).unlink(missing_ok=True)
                self.update.emit({"filepath": dst})
                self._finish(0, "")
            else:
                self._finish(1, f"转换 {fmt.upper()} 失败：{err}")

        p.exited.connect(done)
        p.start()

    def _on_server_stopped(self, reason: str) -> None:
        if not self.cancelled and not self._finished and self._task_id:
            self._timer.stop()
            self._finish(1, reason)

    def _finish(self, code: int, err: str) -> None:
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        self.exited.emit(code, err)


# ---------------- 扫码登录 ----------------
def login_data_path() -> Path | None:
    exe = bbdownt_path()
    return Path(exe).parent / "BBDownT.data" if exe else None


def is_logged_in() -> bool:
    p = login_data_path()
    return bool(p and p.is_file() and p.stat().st_size > 0)


def logout() -> None:
    p = login_data_path()
    if p:
        p.unlink(missing_ok=True)


class BiliLogin(QObject):
    """运行 `BBDownT login`：它把二维码写到工作目录的 qrcode.png，扫码成功后保存 BBDownT.data。"""

    qrReady = Signal(str)       # 二维码图片的本地路径
    status = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._proc: ToolProcess | None = None
        self._dir = ""
        self._qr_shown = 0.0
        self._ok = False
        self._timer = QTimer(self, interval=300)
        self._timer.timeout.connect(self._check_qr)

    def running(self) -> bool:
        return self._proc is not None

    def start(self) -> None:
        if self._proc:
            return
        exe = bbdownt_path()
        if not exe:
            self.finished.emit(False, "找不到 BBDownT.exe")
            return
        self._dir = tempfile.mkdtemp(prefix="bbdownt-login-")
        self._qr_shown = 0.0
        self._ok = False
        p = self._proc = ToolProcess(exe, ["login"], self, cwd=self._dir)
        p.line.connect(self._on_line)
        p.exited.connect(self._on_exit)
        p.start()
        self._timer.start()
        self.status.emit("正在获取二维码…")

    def cancel(self) -> None:
        if self._proc:
            self._proc.cancel()

    def _on_line(self, raw: str) -> None:
        line = strip_log(raw)
        if not line or set(line) <= set("█▀▄ "):
            return  # 控制台打印的字符二维码
        if "登录成功" in line:
            self._ok = True
        self.status.emit(line)

    def _check_qr(self) -> None:
        qr = Path(self._dir) / "qrcode.png"
        if qr.is_file():
            mtime = qr.stat().st_mtime
            if mtime != self._qr_shown:
                self._qr_shown = mtime
                # 复制成新文件名，避免 QML Image 缓存旧二维码
                shown = Path(self._dir) / f"qr_{int(mtime * 1000)}.png"
                shutil.copyfile(qr, shown)
                self.qrReady.emit(str(shown))

    def _on_exit(self, code: int, err: str) -> None:
        self._timer.stop()
        p, self._proc = self._proc, None
        cancelled = bool(p and p.cancelled)
        if p:
            p.deleteLater()
        shutil.rmtree(self._dir, ignore_errors=True)
        if cancelled:
            self.finished.emit(False, "已取消登录")
        elif code == 0 and (self._ok or is_logged_in()):
            self.finished.emit(True, "B 站登录成功")
        else:
            self.finished.emit(False, f"登录失败：{err}")
