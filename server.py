"""
Instagram Reel MCP Server
--------------------------
Read-only tools for a public Instagram Reel URL:

  fetch_instagram_reel   -> video file + metadata only (fast, cached)
  fetch_reel_transcript  -> + speech transcript, no frames (no vision cost)
  analyze_instagram_reel -> + sampled frames, a contact sheet, transcript

No comment / like / share / follow / post capability exists anywhere in
this file — that boundary is enforced by omission, not a toggle.

Analysis happens fresh on every call unless served from local cache.
Nothing here trains, fine-tunes, or updates any model's weights.

Requires on PATH: yt-dlp, ffmpeg
Requires via pip: mcp, faster-whisper, Pillow (see requirements.txt)
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("instagram-reel")

# scrapesmith/instagram-hashtag-scraper, verified via apify.com Nov 2026.
# Community-maintained third-party Actor, not Instagram or Apify official.
APIFY_HASHTAG_ACTOR_ID = "7YASHOuDdgJuPjqsP"
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN")

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "ig_reel_mcp"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Set via env var so this is deployable without editing source:
#   export IG_REEL_COOKIES=/path/to/cookies.txt
# Instagram often requires a logged-in session even for public posts.
COOKIES_FILE: Optional[str] = os.environ.get("IG_REEL_COOKIES") or None

_WHISPER_MODEL_SIZE = "base"
_whisper_model = None


def _reel_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/(reel|p|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(2) if m else None


@mcp.tool()
def fetch_instagram_reel(url: str, force_refresh: bool = False) -> dict:
    """
    Fetch a public Instagram Reel: downloads the video and extracts metadata.
    Read-only — does not comment, like, share, follow, or post anything.
    Served from local cache on repeat calls for the same reel unless
    force_refresh=True.

    Args:
        url: Full Instagram Reel URL, e.g. https://www.instagram.com/reel/XXXXXXXXX/
        force_refresh: bypass the cache and re-download.

    Returns:
        dict with video_path, thumbnail_path, caption, uploader, duration,
        view_count, like_count, comment_count, upload_date, cached —
        or an "error" key.
    """
    if "instagram.com" not in url:
        return {"error": "URL does not look like an Instagram link."}

    reel_id = _reel_id_from_url(url)
    if not force_refresh and reel_id:
        cached_info = DOWNLOAD_DIR / f"{reel_id}.info.json"
        cached_video = DOWNLOAD_DIR / f"{reel_id}.mp4"
        if cached_info.exists() and cached_video.exists():
            info = json.loads(cached_info.read_text())
            thumb = next(DOWNLOAD_DIR.glob(f"{reel_id}*.jpg"), None)
            return {
                "video_path": str(cached_video),
                "thumbnail_path": str(thumb) if thumb else None,
                "caption": info.get("description"),
                "uploader": info.get("uploader") or info.get("uploader_id"),
                "duration_seconds": info.get("duration"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "comment_count": info.get("comment_count"),
                "upload_date": info.get("upload_date"),
                "cached": True,
            }

    out_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist",
        "--write-info-json", "--write-thumbnail",
        "-o", out_template, url,
    ]
    if COOKIES_FILE:
        cmd[1:1] = ["--cookies", COOKIES_FILE]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as e:
        return {
            "error": (
                "Download failed. Instagram may require a logged-in session "
                "(set IG_REEL_COOKIES) or the post may be private, age-gated, "
                "or removed."
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
        "cached": False,
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


def _build_contact_sheet(frames: list, out_dir: Path, cols: int = 5) -> Optional[str]:
    """Combine sampled frames into one grid image so an agent can inspect
    the whole reel in a single vision call instead of one per frame."""
    if not frames:
        return None
    from PIL import Image, ImageDraw, ImageFont

    cell_w, cell_h = 220, 220
    n = len(frames)
    cols = min(cols, n)
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (14, 14, 16))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for i, f in enumerate(frames):
        img = Image.open(f["frame_path"]).convert("RGB")
        img.thumbnail((cell_w - 8, cell_h - 26))
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        sheet.paste(img, (x + (cell_w - img.width) // 2, y + 4))
        label = f"{f['timestamp_seconds']}s"
        draw.rectangle([x, y + cell_h - 18, x + cell_w, y + cell_h], fill=(0, 0, 0))
        draw.text((x + 4, y + cell_h - 15), label, fill=(255, 255, 255), font=font)

    out_path = out_dir / "contact_sheet.jpg"
    sheet.save(out_path, quality=85)
    return str(out_path)


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(_WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def _transcribe_cached(video_path: Path) -> str:
    """Transcribe once per video, cache to disk so repeat calls (from
    fetch_reel_transcript or analyze_instagram_reel) skip Whisper entirely."""
    cache_path = video_path.with_suffix(".transcript.txt")
    if cache_path.exists():
        return cache_path.read_text()
    model = _get_whisper_model()
    segments, _ = model.transcribe(str(video_path))
    text = " ".join(seg.text.strip() for seg in segments).strip()
    cache_path.write_text(text)
    return text


@mcp.tool()
def fetch_reel_transcript(url: str) -> dict:
    """
    Lightweight: downloads (or reuses cache) and returns only the speech
    transcript plus text metadata — no frame extraction, no images, no
    vision tokens spent. Use this when the question is about what was
    SAID, not what is SHOWN.

    Returns:
        dict with transcript, caption, uploader, duration_seconds,
        view_count, like_count, comment_count, upload_date —
        or an "error" key.
    """
    base = fetch_instagram_reel(url)
    if "error" in base:
        return base
    video_path = Path(base["video_path"]) if base.get("video_path") else None
    if not video_path or not video_path.exists():
        return {"error": "Video file missing after download; cannot transcribe."}

    try:
        transcript = _transcribe_cached(video_path)
    except Exception as e:
        return {"error": "Transcription failed.", "details": str(e)[-500:]}

    return {
        "transcript": transcript,
        "caption": base.get("caption"),
        "uploader": base.get("uploader"),
        "duration_seconds": base.get("duration_seconds"),
        "view_count": base.get("view_count"),
        "like_count": base.get("like_count"),
        "comment_count": base.get("comment_count"),
        "upload_date": base.get("upload_date"),
    }


@mcp.tool()
def analyze_instagram_reel(
    url: str,
    frame_interval_seconds: float = 1.5,
    max_frames: int = 30,
) -> dict:
    """
    Full analysis: downloads the video, samples frames, builds one combined
    contact-sheet image from them, and transcribes the audio — so the
    calling AI sees what is shown and said, not just the caption.

    To minimize vision-token cost, read `contact_sheet_path` (one image)
    before opening individual entries in `frames` (up to max_frames images).

    Request-time analysis only — no training, no persisted learning beyond
    the on-disk cache.

    Returns:
        dict with video_path, frames, contact_sheet_path, transcript,
        caption, uploader, duration_seconds, view_count, like_count,
        comment_count, upload_date — or an "error" key.
    """
    base = fetch_instagram_reel(url)
    if "error" in base:
        return base

    video_path = Path(base["video_path"]) if base.get("video_path") else None
    if not video_path or not video_path.exists():
        return {"error": "Video file missing after download; cannot analyze."}

    try:
        frames = _extract_frames(video_path, frame_interval_seconds, max_frames)
        base["frames"] = frames
        base["contact_sheet_path"] = _build_contact_sheet(frames, video_path.parent)
    except subprocess.CalledProcessError as e:
        base["frames"] = []
        base["contact_sheet_path"] = None
        base["frame_extraction_error"] = (e.stderr or str(e))[-500:]
    except FileNotFoundError:
        base["frames"] = []
        base["contact_sheet_path"] = None
        base["frame_extraction_error"] = "ffmpeg is not installed or not on PATH."

    try:
        base["transcript"] = _transcribe_cached(video_path)
    except Exception as e:
        base["transcript"] = ""
        base["transcription_error"] = str(e)[-500:]

    return base


@mcp.tool()
def discover_trending_by_hashtag(hashtag: str, limit: int = 5, include_transcripts: bool = False) -> dict:
    """
    Find top public reels for a hashtag. There is no real Instagram
    "genre" taxonomy, so map a genre/niche to the closest hashtag
    yourself (e.g. "comedy" -> "comedyreels", "fitness" -> "gymtok").

    EXPERIMENTAL - different mechanism than the other tools. yt-dlp has
    no Instagram hashtag/discovery extractor, so this calls a
    third-party paid Apify Actor (scrapesmith/instagram-hashtag-scraper)
    over HTTPS instead. Requires your own Apify account and an
    APIFY_API_TOKEN env var (free tier: $5/month credit; 5 results costs
    a fraction of a cent). Field names here are based on the actor's
    published docs as of Nov 2026 and have NOT been verified end-to-end
    from this build environment (no network path to apify.com here) -
    it is community-maintained and its output shape can change without
    notice. Run it once and check the output before relying on it.

    Args:
        hashtag: hashtag to search, with or without '#'.
        limit: how many top reels to return. The actor does not
            guarantee results pre-sorted by engagement, so this
            over-fetches and ranks by likes_count locally.
        include_transcripts: if True, also downloads and transcribes
            each returned reel in this same call - real added time and
            cost (up to `limit` full downloads + Whisper runs). Default
            False: return URLs/captions/counts only, and let the caller
            decide which ones are worth the deeper fetch via
            fetch_reel_transcript or analyze_instagram_reel.

    Returns:
        dict with hashtag, reels (list of url, caption, likes_count,
        comments_count, owner_username, type, and transcript if
        requested) - or an "error" key.
    """
    if not APIFY_API_TOKEN:
        return {
            "error": (
                "APIFY_API_TOKEN is not set. Create a free Apify account, "
                "get an API token from the Apify Console, and set it as an "
                "env var in your MCP client's server config."
            )
        }

    tag = hashtag.lstrip("#").strip()
    if not tag:
        return {"error": "Empty hashtag."}

    fetch_count = max(limit * 4, 20)  # over-fetch so local ranking has something to rank
    try:
        import requests
        resp = requests.post(
            f"https://api.apify.com/v2/acts/{APIFY_HASHTAG_ACTOR_ID}/run-sync-get-dataset-items",
            params={"token": APIFY_API_TOKEN},
            json={"hashtags": [tag], "maxResultsPerHashtag": fetch_count},
            timeout=90,
        )
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        return {"error": "Apify request failed.", "details": str(e)[-500:]}

    videos = [it for it in items if it.get("type") == "video" or it.get("productType") == "reel"]
    videos.sort(key=lambda it: it.get("likesCount", 0), reverse=True)
    top = videos[:limit]

    if not top:
        return {"hashtag": tag, "reels": [], "note": "No video/reel results found for this hashtag."}

    results = []
    for it in top:
        entry = {
            "url": it.get("url"),
            "caption": it.get("caption"),
            "likes_count": it.get("likesCount"),
            "comments_count": it.get("commentsCount"),
            "owner_username": it.get("ownerUsername"),
            "type": it.get("type"),
        }
        if include_transcripts and entry["url"]:
            t = fetch_reel_transcript(entry["url"])
            entry["transcript"] = t.get("transcript", "")
            if "error" in t:
                entry["transcript_error"] = t["error"]
        results.append(entry)

    return {"hashtag": tag, "reels": results}


if __name__ == "__main__":
    mcp.run()
