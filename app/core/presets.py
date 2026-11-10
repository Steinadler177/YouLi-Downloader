"""下载预设：名称 -> 传给 yt-dlp 的参数 / 传给 BBDownT 的任务选项。想加新预设只改这里。"""
from __future__ import annotations

from dataclasses import dataclass, field

# B 站清晰度名称（BBDownT -q 使用），从高到低
_BILI_TIERS = [
    "8K 超高清", "杜比视界", "HDR 真彩", "4K 超清",
    "1080P 60帧", "1080P 高码率", "1080P 高清",
    "720P 60帧", "720P 高清", "480P 清晰", "360P 流畅",
]


def _bili_dfn(max_tier: str) -> str:
    """不超过 max_tier 的清晰度优先级列表（BBDownT 取第一个可用的）。"""
    return ",".join(_BILI_TIERS[_BILI_TIERS.index(max_tier):])


@dataclass(frozen=True)
class Preset:
    name: str
    args: tuple[str, ...]                                  # yt-dlp 参数
    bili: dict = field(default_factory=dict)               # BBDownT 任务选项（ServeRequestOptions 字段）
    audio_format: str = ""                                 # 非空：BBDownT 下载后用 ffmpeg 转成该格式


def _video(height: int, bili_max: str) -> Preset:
    # -S 排序：分辨率不超过 height，优先 mp4/m4a，合并时优先封装为 mp4
    return Preset(
        f"{height}p 视频",
        ("-S", f"res:{height},ext:mp4:m4a", "--merge-output-format", "mp4/mkv"),
        {"DfnPriority": _bili_dfn(bili_max)},
    )


PRESETS: list[Preset] = [
    Preset("最佳画质", ("-f", "bv*+ba/b", "--merge-output-format", "mp4/mkv")),
    _video(2160, "4K 超清"),
    _video(1440, "1080P 60帧"),   # B 站没有 1440p，按 1080P 处理
    _video(1080, "1080P 60帧"),
    _video(720, "720P 60帧"),
    _video(480, "480P 清晰"),
    Preset("仅音频 MP3", ("-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0"),
           {"AudioOnly": True}, audio_format="mp3"),
    Preset("仅音频 M4A", ("-f", "ba[ext=m4a]/ba/b", "-x", "--audio-format", "m4a"),
           {"AudioOnly": True}),
]


def get_preset(index: int) -> Preset:
    if 0 <= index < len(PRESETS):
        return PRESETS[index]
    return PRESETS[0]
