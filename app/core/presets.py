"""下载预设：名称 -> 传给 yt-dlp 的参数。想加新预设只改这里。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    args: tuple[str, ...]


def _video(height: int) -> Preset:
    # -S 排序：分辨率不超过 height，优先 mp4/m4a，合并时优先封装为 mp4
    return Preset(
        f"{height}p 视频",
        ("-S", f"res:{height},ext:mp4:m4a", "--merge-output-format", "mp4/mkv"),
    )


PRESETS: list[Preset] = [
    Preset("最佳画质", ("-f", "bv*+ba/b", "--merge-output-format", "mp4/mkv")),
    _video(2160),
    _video(1440),
    _video(1080),
    _video(720),
    _video(480),
    Preset("仅音频 MP3", ("-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0")),
    Preset("仅音频 M4A", ("-f", "ba[ext=m4a]/ba/b", "-x", "--audio-format", "m4a")),
]


def get_preset(index: int) -> Preset:
    if 0 <= index < len(PRESETS):
        return PRESETS[index]
    return PRESETS[0]
