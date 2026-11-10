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


def find_tool(name: str) -> str | None:
    """优先使用 bin/ 下的外部工具，找不到再回退到系统 PATH。"""
    local = BIN_DIR / f"{name}.exe"
    if local.is_file():
        return str(local)
    return shutil.which(name)


@dataclass
class Settings:
    output_dir: str = str(Path.home() / "Downloads")
    filename_template: str = "%(title)s [%(id)s].%(ext)s"
    cookies_browser: str = ""          # "" / firefox / chrome / edge / brave ...
    max_concurrent: int = 2
    download_playlist: bool = False
    dark_theme: bool = True
    last_preset: int = 0
    extra_args: list[str] = field(default_factory=list)  # 高级：追加给 yt-dlp 的参数

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(CONFIG_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        defaults = cls()
        kwargs = {}
        for f in fields(cls):
            if f.name in data and isinstance(data[f.name], type(getattr(defaults, f.name))):
                kwargs[f.name] = data[f.name]
        return cls(**kwargs)

    def save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), "utf-8")
        except OSError:
            pass
