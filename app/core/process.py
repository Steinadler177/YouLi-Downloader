"""QProcess 封装：按行读取输出、UTF-8、可靠地结束整个进程树。"""
from __future__ import annotations

import subprocess

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ToolProcess(QObject):
    """运行一个外部命令。

    collect=False：stdout 按行通过 line 信号发出（stderr 合并进来）。
    collect=True ：stdout 全部收集到 self.stdout（用于 -J 这种大 JSON），stderr 按行发出。
    """

    line = Signal(str)
    exited = Signal(int, str)  # 退出码, 错误摘要（成功时为空）

    def __init__(self, program: str, args: list[str], parent: QObject | None = None, collect: bool = False):
        super().__init__(parent)
        self.collect = collect
        self.stdout = b""
        self.cancelled = False
        self._buf = {"out": b"", "err": b""}
        self._last_error = ""
        self._last_line = ""

        p = self._proc = QProcess(self)
        p.setProgram(program)
        p.setArguments(args)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUTF8", "1")
        p.setProcessEnvironment(env)
        if not collect:
            p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._read("out"))
        p.readyReadStandardError.connect(lambda: self._read("err"))
        p.finished.connect(self._on_finished)
        p.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        self._proc.start()

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.NotRunning

    def cancel(self) -> None:
        """yt-dlp.exe 是 PyInstaller 单文件程序（父子两个进程），还可能带 ffmpeg 子进程，
        QProcess.kill() 只能杀掉最外层，所以用 taskkill /T 结束整棵进程树。"""
        self.cancelled = True
        if not self.is_running():
            return
        pid = self._proc.processId()
        if pid:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=_NO_WINDOW)
        self._proc.kill()

    # ---- internal ----
    def _read(self, channel: str) -> None:
        if channel == "err" and not self.collect:
            return  # 合并通道模式下 stderr 已并入 stdout
        # 注意：不要用 setReadChannel()+readAll().data()，在 PySide6 6.12 上读空缓冲区会访问冲突崩溃
        qba = self._proc.readAllStandardOutput() if channel == "out" else self._proc.readAllStandardError()
        if qba.isEmpty():
            return
        data = bytes(qba)
        if self.collect and channel == "out":
            self.stdout += data
            return
        buf = self._buf[channel] + data
        *lines, rest = buf.split(b"\n")
        self._buf[channel] = rest
        for raw in lines:
            self._emit_line(raw)

    def _emit_line(self, raw: bytes) -> None:
        text = raw.decode("utf-8", errors="replace").rstrip("\r")
        if not text:
            return
        if text.startswith("ERROR:"):
            self._last_error = text[6:].strip()
        self._last_line = text
        self.line.emit(text)

    def _flush(self) -> None:
        for ch, rest in self._buf.items():
            if rest and not (self.collect and ch == "out"):
                self._emit_line(rest)
            self._buf[ch] = b""

    def _on_finished(self, code: int, status) -> None:
        self._read("out")
        self._read("err")
        self._flush()
        if self.cancelled:
            self.exited.emit(code if code else -1, "已取消")
        elif code == 0 and status == QProcess.NormalExit:
            self.exited.emit(0, "")
        else:
            self.exited.emit(code or -1, self._last_error or self._last_line or f"退出码 {code}")

    def _on_error(self, err) -> None:
        if err == QProcess.FailedToStart:
            self.exited.emit(-1, f"无法启动 {self._proc.program()}")
