"""构造 yt-dlp 命令行参数。纯函数，不依赖 Qt，便于测试。"""
from __future__ import annotations

from .config import Settings
from .presets import Preset

# 通过 --print / --progress-template 让 yt-dlp 输出带标记、可解析的行
PROGRESS_TAG = "[progress]"
ITEM_TAG = "[item]"
DONE_TAG = "[done]"


def looks_like_playlist_url(url: str) -> bool:
    """链接本身是列表页。带 list= 的单视频页不在此列，由 download_playlist 开关控制。"""
    u = url.lower()
    return any(tok in u for tok in (
        "/playlist?", "/playlist/", "/playlists", "/sets/", "/album/",
    )) or u.rstrip("/").endswith("/playlist")


def _common(settings: Settings, ffmpeg: str | None, *, yes_playlist: bool) -> list[str]:
    # --encoding utf-8：强制元数据/打印用 UTF-8，避免 Windows 控制台 GBK 导致标题乱码
    args = ["--newline", "--no-colors", "--encoding", "utf-8"]
    if ffmpeg:
        args += ["--ffmpeg-location", ffmpeg]
    if settings.cookies_browser:
        args += ["--cookies-from-browser", settings.cookies_browser]
    args.append("--yes-playlist" if yes_playlist else "--no-playlist")
    return args


def download_args(url: str, preset: Preset, settings: Settings, ffmpeg: str | None,
                  output_dir: str | None = None) -> list[str]:
    """单条下载：始终 --no-playlist（播放列表已在队列里展开成多任务）。"""
    out = output_dir or settings.output_dir
    return [
        *_common(settings, ffmpeg, yes_playlist=False),
        "--progress",
        "--progress-template", f"download:{PROGRESS_TAG}%(progress)j",
        "--print", f"before_dl:{ITEM_TAG}%(playlist_index|)s|%(n_entries|)s|%(title)s",
        "--print", f"after_move:{DONE_TAG}%(filepath)s",
        "--no-mtime",
        "-P", out,
        "-o", settings.filename_template,
        *preset.args,
        *settings.extra_args,
        "--", url,
    ]


def probe_args(url: str, settings: Settings) -> list[str]:
    """探测：列表页或开启“下载整个播放列表”时拉全表，否则只解析当前条目。"""
    yes = settings.download_playlist or looks_like_playlist_url(url)
    return [*_common(settings, None, yes_playlist=yes), "-J", "--flat-playlist", "--", url]
