"""解析 yt-dlp 输出的进度 JSON / 视频信息 JSON，并格式化成界面文本。纯函数。"""
from __future__ import annotations

import json


def human_size(n: float | None) -> str:
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def human_time(sec: float | None) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_progress(raw: str) -> dict | None:
    """把 --progress-template 的 JSON 转成界面字段；解析失败返回 None。"""
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    done = d.get("downloaded_bytes") or 0
    total = d.get("total_bytes") or d.get("total_bytes_estimate")
    if total:
        frac = min(done / total, 1.0)
    elif d.get("fragment_count"):
        frac = (d.get("fragment_index") or 0) / d["fragment_count"]
    else:
        frac = -1.0  # 未知总大小 -> 不确定进度
    size = human_size(total) if total else human_size(done)
    if total and d.get("status") == "downloading":
        size = f"{human_size(done)} / {human_size(total)}"
    speed = d.get("speed")
    return {
        "state": d.get("status", ""),
        "progress": frac,
        "size": size,
        "speed": f"{human_size(speed)}/s" if speed else "",
        "eta": human_time(d.get("eta")),
    }


def summarize_info(info: dict) -> dict:
    """把 yt-dlp -J 的结果压缩成界面需要的字段。"""
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        return {
            "title": info.get("title") or "播放列表",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "duration": "",
            "thumbnail": _thumb(info),
            "isPlaylist": True,
            "count": len(entries),
            "heights": "",
        }
    heights = sorted(
        {f["height"] for f in info.get("formats") or [] if f.get("height") and f.get("vcodec") != "none"},
        reverse=True,
    )
    return {
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": human_time(info.get("duration")),
        "thumbnail": _thumb(info),
        "isPlaylist": False,
        "count": 1,
        "heights": " / ".join(f"{h}p" for h in heights[:8]),
    }


def _thumb(info: dict) -> str:
    thumbs = [t for t in info.get("thumbnails") or [] if t.get("url")]
    # 取一张中等尺寸的，避免拉取超大图
    sized = [t for t in thumbs if (t.get("width") or 0) and t["width"] <= 640]
    if sized:
        return max(sized, key=lambda t: t["width"])["url"]
    return info.get("thumbnail") or (thumbs[-1]["url"] if thumbs else "")
