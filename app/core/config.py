"""路径与用户设置。

- APP_DIR：程序所在目录（打包后是 exe 所在目录），放 bin/ 与 config.json，可写。
- RES_DIR：只读资源目录（QML、图标）。打包后位于 PyInstaller 的 _internal 下。
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _res_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "app"
    return Path(__file__).resolve().parents[1]


APP_DIR = _app_dir()
RES_DIR = _res_dir()
BIN_DIR = APP_DIR / "bin"
CONFIG_PATH = APP_DIR / "config.json"


def safe_dirname(name: str, fallback: str = "playlist") -> str:
    """把播放列表标题收成可用的 Windows 文件夹名。"""
    bad = '<>:"/\\|?*\0'
    cleaned = "".join("_" if c in bad else c for c in (name or "").strip()).rstrip(" .")
    cleaned = " ".join(cleaned.split())  # 压缩空白
    return (cleaned or fallback)[:80]


def find_tool(name: str) -> str | None:
    """优先使用 bin/ 下的外部工具，找不到再回退到系统 PATH。"""
    local = BIN_DIR / f"{name}.exe"
    if local.is_file():
        return str(local)
    return shutil.which(name)


QUEUE_PATH = APP_DIR / "queue.json"


@dataclass
class Settings:
    output_dir: str = str(Path.home() / "Downloads")
    filename_template: str = "%(title)s [%(id)s].%(ext)s"
    cookies_browser: str = ""          # "" / firefox / chrome / edge / brave ...
    download_playlist: bool = False
    dark_theme: bool = True
    last_preset: int = 0
    extra_args: list[str] = field(default_factory=list)  # 高级：追加给 yt-dlp 的参数
    use_bbdownt: bool = True           # B 站链接交给 BBDownT（找不到 BBDownT 时自动回退 yt-dlp）
    bili_api: str = ""                 # "" = WEB / "tv" / "app"：BBDownT 解析接口
    auto_start_queue: bool = False     # 添加任务后自动开始队列
    window_x: int = -1
    window_y: int = -1
    window_w: int = 1100
    window_h: int = 740
    window_maximized: bool = False
    # 启动加速：缓存外部工具版本，避免一开机就跑 yt-dlp --version（单文件自解压很慢）
    cached_ytdlp_version: str = ""
    cached_ytdlp_mtime: float = 0.0
    cached_bbdownt_version: str = ""
    cached_bbdownt_mtime: float = 0.0

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(CONFIG_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        defaults = cls()
        kwargs = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            val = data[f.name]
            expected = type(getattr(defaults, f.name))
            # JSON 数字常为 int，float 字段也要收下
            if expected is float and isinstance(val, (int, float)):
                kwargs[f.name] = float(val)
            elif isinstance(val, expected):
                kwargs[f.name] = val
        return cls(**kwargs)

    def save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), "utf-8")
        except OSError:
            pass
