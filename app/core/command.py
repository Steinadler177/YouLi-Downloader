"""构造 yt-dlp 命令行参数。纯函数，不依赖 Qt，便于测试。"""
from __future__ import annotations

from .config import Settings
from .presets import Preset

# 通过 --print / --progress-template 让 yt-dlp 输出带标记、可解析的行
PROGRESS_TAG = "[progress]"
ITEM_TAG = "[item]"
DONE_TAG = "[done]"


def _common(settings: Settings, ffmpeg: str | None) -> list[str]:
    # --encoding utf-8：强制元数据/打印用 UTF-8，避免 Windows 控制台 GBK 导致标题乱码
    args = ["--newline", "--no-colors", "--encoding", "utf-8"]
    if ffmpeg:
        args += ["--ffmpeg-location", ffmpeg]
    if settings.cookies_browser:
        args += ["--cookies-from-browser", settings.cookies_browser]
    args.append("--yes-playlist" if settings.download_playlist else "--no-playlist")
    return args


def download_args(url: str, preset: Preset, settings: Settings, ffmpeg: str | None) -> list[str]:
    return [
        *_common(settings, ffmpeg),
        "--progress",
        "--progress-template", f"download:{PROGRESS_TAG}%(progress)j",
        "--print", f"before_dl:{ITEM_TAG}%(playlist_index|)s|%(n_entries|)s|%(title)s",
        "--print", f"after_move:{DONE_TAG}%(filepath)s",
        "--no-mtime",
        "-P", settings.output_dir,
        "-o", settings.filename_template,
        *preset.args,
        *settings.extra_args,
        "--", url,
    ]


def probe_args(url: str, settings: Settings) -> list[str]:
    return [*_common(settings, None), "-J", "--flat-playlist", "--", url]
