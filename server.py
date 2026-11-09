"""
Instagram Reel MCP Server
--------------------------
Read-only tools for a public Instagram Reel URL:

  fetch_instagram_reel   -> video file + metadata only (fast)
  analyze_instagram_reel -> video + metadata + sampled frames + speech
                             transcript (slower, fuller picture)

No comment / like / share / follow / post capability exists anywhere
in this file — that boundary is enforced by omission, not a toggle.

Analysis happens fresh on every call. Nothing here trains, fine-tunes,
or updates any model's weights, and nothing persists between calls
except the downloaded files on disk.

Requires on PATH: yt-dlp, ffmpeg
Requires via pip: mcp, faster-whisper (see requirements.txt)
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("instagram-reel")

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "ig_reel_mcp"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Optional: path to a cookies.txt file (Netscape format) exported from a
# logged-in browser session. Instagram often requires this for reliable
# access, even to public posts. Leave as None to attempt cookie-less access.
COOKIES_FILE: Optional[str] = None  # e.g. "/home/you/ig_cookies.txt"

# Loaded lazily on first transcription call, then cached for the process
# lifetime. "base" balances speed and accuracy on CPU; switch to "small"
# or "medium" for better accuracy at the cost of speed.
_WHISPER_MODEL_SIZE = "base"
_whisper_model = None


@mcp.tool()
def fetch_instagram_reel(url: str) -> dict:
    """
    Fetch a public Instagram Reel: downloads the video and extracts metadata.
    Read-only — does not comment, like, share, follow, or post anything.

    Args:
        url: Full Instagram Reel URL, e.g. https://www.instagram.com/reel/XXXXXXXXX/

    Returns:
        dict with video_path, thumbnail_path, caption, uploader, duration,
        view_count, like_count, comment_count, upload_date — or an "error" key.
    """
    if "instagram.com" not in url:
        return {"error": "URL does not look like an Instagram link."}

    out_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--write-info-json",
        "--write-thumbnail",
        "-o", out_template,
        url,
    ]
    if COOKIES_FILE:
        cmd[1:1] = ["--cookies", COOKIES_FILE]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as e:
        return {
            "error": (
                "Download failed. Instagram may require a logged-in session "
                "(set COOKIES_FILE at the top of server.py) or the post may "
                "be private, age-gated, or removed."
            ),
            "details": (e.stderr or str(e))[-800:],
        }
    except subprocess.TimeoutExpired:
        return {"error": "Download timed out after 120s."}
    except FileNotFoundError:
        return {"error": "yt-dlp is not installed or not on PATH. Run: pip install yt-dlp"}

    info_files = sorted(
        DOWNLOAD_DIR.glob("*.info.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not info_files:
        return {"error": "No metadata file produced; download may have failed silently."}

    info = json.loads(info_files[0].read_text())
    video_id = info.get("id")
    video_path = next(DOWNLOAD_DIR.glob(f"{video_id}.mp4"), None)
    thumb_path = next(DOWNLOAD_DIR.glob(f"{video_id}*.jpg"), None)

    return {
        "video_path": str(video_path) if video_path else None,
        "thumbnail_path": str(thumb_path) if thumb_path else None,
        "caption": info.get("description"),
        "uploader": info.get("uploader") or info.get("uploader_id"),
        "duration_seconds": info.get("duration"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "upload_date": info.get("upload_date"),
    }


def _extract_frames(video_path: Path, interval_seconds: float, max_frames: int) -> list:
    frames_dir = video_path.parent / f"{video_path.stem}_frames"
    frames_dir.mkdir(exist_ok=True)
    for f in frames_dir.glob("frame_*.jpg"):
        f.unlink()

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps=1/{interval_seconds}",
        "-q:v", "3",
        str(frames_dir / "frame_%03d.jpg"),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)

    frame_files = sorted(frames_dir.glob("frame_*.jpg"))[:max_frames]
    return [
        {"timestamp_seconds": round(i * interval_seconds, 1), "frame_path": str(p)}
        for i, p in enumerate(frame_files)
    ]


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(_WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def _transcribe(video_path: Path) -> str:
    model = _get_whisper_model()
    segments, _ = model.transcribe(str(video_path))
    return " ".join(seg.text.strip() for seg in segments).strip()


@mcp.tool()
def analyze_instagram_reel(
    url: str,
    frame_interval_seconds: float = 1.5,
    max_frames: int = 30,
) -> dict:
    """
    Full analysis of a public Instagram Reel: downloads the video, samples
    frames across its full length for visual inspection, transcribes the
    spoken audio, and returns metadata — so the calling AI sees what is
    actually shown and said in the reel, not just the caption.

    This is request-time analysis only. It does not train or fine-tune
    any model, and nothing persists across calls except downloaded files.

    Args:
        url: Full Instagram Reel URL.
        frame_interval_seconds: seconds between sampled frames (default 1.5).
        max_frames: cap on frames returned, to bound cost (default 30).

    Returns:
        dict with video_path, frames (list of {timestamp_seconds, frame_path}),
        transcript, caption, uploader, duration_seconds, view_count,
        like_count, comment_count, upload_date — or an "error" key.
    """
    base = fetch_instagram_reel(url)
    if "error" in base:
        return base

    video_path = Path(base["video_path"]) if base.get("video_path") else None
    if not video_path or not video_path.exists():
        return {"error": "Video file missing after download; cannot analyze."}

    try:
        base["frames"] = _extract_frames(video_path, frame_interval_seconds, max_frames)
    except subprocess.CalledProcessError as e:
        base["frames"] = []
        base["frame_extraction_error"] = (e.stderr or str(e))[-500:]
    except FileNotFoundError:
        base["frames"] = []
        base["frame_extraction_error"] = "ffmpeg is not installed or not on PATH."

    try:
        base["transcript"] = _transcribe(video_path)
    except Exception as e:
        base["transcript"] = ""
        base["transcription_error"] = str(e)[-500:]

    return base


if __name__ == "__main__":
    mcp.run()
