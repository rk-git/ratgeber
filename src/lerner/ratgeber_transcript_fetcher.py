"""
ratgeber_transcript_fetcher.py - Linbit YouTube transcript harvester

Fetches all video transcripts from the LINBIT YouTube channel,
cleans them, chunks them, and saves them to data/docs/transcripts/
for ingestion by ingest_once.py into ChromaDB.

Part of the Lerner subsystem — feeds Ratgeber's fine-tuning pipeline
with knowledge from Linbit presentations, demos, and webinars.

BDD spec: docs/lerner/lerner.feature

copyright (c) 2026 Always Up Networks LLC. MIT License.

Usage:
  python src/lerner/ratgeber_transcript_fetcher.py
  python src/lerner/ratgeber_transcript_fetcher.py --from-cache
  python src/lerner/ratgeber_transcript_fetcher.py --video-id dQw4w9WgXcQ
  python src/lerner/ratgeber_transcript_fetcher.py --dry-run
"""

import argparse
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from typing import Final
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CHANNEL_URL: Final[str] = "https://www.youtube.com/@linbit"
MIN_DURATION_SECONDS: Final[int] = 60       # skip videos shorter than this
CHUNK_SIZE_WORDS: Final[int] = 500          # target words per chunk
PREFERRED_LANGUAGES: Final[list[str]] = ["en", "de"]  # English first, German fallback
PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent
CACHE_DIR: Final[Path] = PROJECT_ROOT / ".cache" / "transcripts"
TRANSCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "data" / "docs" / "transcripts"
CHANNEL_CACHE: Final[Path] = PROJECT_ROOT / ".cache" / "channel_videos.json"

# ---------------------------------------------------------------------------
# TERMINOLOGY CORRECTIONS
#
# Auto-generated transcripts mangle technical terms.
# These replacements are applied before chunking.
#
# ENRICH: add corrections as you discover new mangled terms.
# Pattern is (regex_pattern, replacement) — applied in order.
# ---------------------------------------------------------------------------

TERM_CORRECTIONS = [
    # DRBD variations
    (r'\bD\s*R\s*B\s*D\b', 'DRBD'),
    (r'\bderby\b', 'DRBD'),
    (r'\bd\.r\.b\.d\b', 'DRBD'),

    # LINSTOR variations
    (r'\blin\s+store\b', 'LINSTOR'),
    (r'\blin\s*stor\b', 'LINSTOR'),
    (r'\blinstor\b', 'LINSTOR'),           # fix lowercase

    # LINBIT variations
    (r'\blin\s*bit\b', 'LINBIT'),
    (r'\blinbit\b', 'LINBIT'),             # fix lowercase

    # Other product names
    (r'\bpiraeus\b', 'Piraeus'),
    (r'\bdrbd\b', 'DRBD'),                 # fix lowercase
    (r'\bdrbdadm\b', 'drbdadm'),           # keep lowercase — it's a command
    (r'\blinstor gateway\b', 'LINSTOR Gateway'),
    (r'\bwindrbd\b', 'WinDRBD'),

    # Sponsor/intro segment markers to strip later
    (r"today'?s? (video )?is sponsored by.*", ''),
    (r'this video is brought to you by.*', ''),
]

# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class VideoMeta:
    video_id: str
    title: str
    duration: int       # seconds
    upload_date: str


@dataclass
class TranscriptChunk:
    video_id: str
    video_title: str
    chunk_index: int
    text: str
    start_time: float   # seconds from start of video
    source: str = "youtube:linbit"


# ---------------------------------------------------------------------------
# STEP 1: Fetch video list from channel
# ---------------------------------------------------------------------------

def fetch_channel_videos(channel_url: str, from_cache: bool = False) -> list[VideoMeta]:
    """
    Use yt-dlp to fetch all video IDs and metadata from the channel.
    Results cached to .cache/channel_videos.json.

    ENRICH: add --dateafter flag to fetch only recent videos for
    incremental runs — e.g. yt-dlp --dateafter 20240101
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if from_cache and CHANNEL_CACHE.exists():
        logging.info(f"[fetch] loading channel videos from cache")
        raw = json.loads(CHANNEL_CACHE.read_text())
        videos = [VideoMeta(**v) for v in raw]
        logging.info(f"[fetch] loaded {len(videos)} videos from cache")
        return videos

    logging.info(f"[fetch] fetching video list from {channel_url}")

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(duration)s\t%(upload_date)s",
        "--no-warnings",
        channel_url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logging.error(f"[fetch] yt-dlp error: {result.stderr}")
            return []

        videos = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            video_id, title, duration_str, upload_date = parts[:4]
            try:
                duration = int(duration_str) if duration_str != "NA" else 0
            except ValueError:
                duration = 0
            videos.append(VideoMeta(
                video_id=video_id,
                title=title,
                duration=duration,
                upload_date=upload_date,
            ))

        # Cache results
        CHANNEL_CACHE.write_text(json.dumps(
            [v.__dict__ for v in videos], indent=2
        ))
        logging.info(f"[fetch] found {len(videos)} videos, cached to {CHANNEL_CACHE}")
        return videos

    except subprocess.TimeoutExpired:
        logging.error("[fetch] yt-dlp timed out")
        return []
    except FileNotFoundError:
        logging.error("[fetch] yt-dlp not found — install with: pip install yt-dlp")
        return []


# ---------------------------------------------------------------------------
# STEP 2: Fetch transcript for a single video
# ---------------------------------------------------------------------------

def fetch_transcript(video: VideoMeta) -> Optional[list[dict]]:
    """
    Fetch transcript for a single video using youtube-transcript-api.
    Prefers English, falls back to German.
    Returns list of {text, start, duration} dicts, or None if unavailable.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video.video_id)

        # Try preferred languages in order
        for lang in PREFERRED_LANGUAGES:
            try:
                transcript = transcript_list.find_transcript([lang])
                segments = transcript.fetch()
                logging.info(
                    f"[transcript] {video.video_id} — fetched {len(segments)} "
                    f"segments ({lang})"
                )
                return segments
            except Exception:
                continue

        logging.warning(f"[transcript] {video.video_id} — no EN/DE transcript available")
        return None

    except NoTranscriptFound:
        logging.warning(f"[transcript] {video.video_id} — no transcript found")
        return None
    except TranscriptsDisabled:
        logging.warning(f"[transcript] {video.video_id} — transcripts disabled")
        return None
    except Exception as e:
        logging.warning(f"[transcript] {video.video_id} — error: {e}")
        return None


# ---------------------------------------------------------------------------
# STEP 3: Clean transcript
# ---------------------------------------------------------------------------

def clean_transcript(segments: list[dict]) -> list[dict]:
    """
    Fix mangled technical terminology in auto-generated transcripts.
    Applied per segment to preserve timestamp metadata.

    ENRICH: add corrections to TERM_CORRECTIONS as new terms are discovered.
    """
    cleaned = []
    for seg in segments:
        text = seg.get("text", "")

        # Apply all term corrections
        for pattern, replacement in TERM_CORRECTIONS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Strip leading/trailing whitespace
        text = text.strip()

        # Skip empty segments after cleaning
        if not text:
            continue

        cleaned.append({
            "text": text,
            "start": seg.get("start", 0.0),
            "duration": seg.get("duration", 0.0),
        })

    return cleaned


# ---------------------------------------------------------------------------
# STEP 4: Chunk transcript into passages
# ---------------------------------------------------------------------------

def chunk_transcript(video: VideoMeta, segments: list[dict]) -> list[TranscriptChunk]:
    """
    Split cleaned transcript segments into chunks of ~CHUNK_SIZE_WORDS words.
    Each chunk retains the start timestamp of its first segment.

    Consistent with ingest_once.py chunking approach — sentence-aware
    boundaries where possible (segments are natural sentence units from
    YouTube's auto-captioning).
    """
    chunks = []
    buffer_texts = []
    buffer_start = 0.0
    word_count = 0

    for i, seg in enumerate(segments):
        text = seg["text"]
        words = len(text.split())

        if i == 0:
            buffer_start = seg["start"]

        buffer_texts.append(text)
        word_count += words

        if word_count >= CHUNK_SIZE_WORDS:
            chunks.append(TranscriptChunk(
                video_id=video.video_id,
                video_title=video.title,
                chunk_index=len(chunks),
                text=" ".join(buffer_texts),
                start_time=buffer_start,
            ))
            buffer_texts = []
            buffer_start = seg["start"]
            word_count = 0

    # Flush remaining buffer
    if buffer_texts:
        chunks.append(TranscriptChunk(
            video_id=video.video_id,
            video_title=video.title,
            chunk_index=len(chunks),
            text=" ".join(buffer_texts),
            start_time=buffer_start,
        ))

    return chunks


# ---------------------------------------------------------------------------
# STEP 5: Save chunks as .txt files for ingest_once.py
# ---------------------------------------------------------------------------

def save_chunks(chunks: list[TranscriptChunk]) -> int:
    """
    Save each chunk as a .txt file under data/docs/transcripts/.
    Format is consistent with what ingest_once.py expects.

    Filename: {video_id}_chunk_{n}.txt
    Content:  metadata header + chunk text

    Returns number of chunks saved.
    """
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for chunk in chunks:
        filename = TRANSCRIPTS_DIR / f"{chunk.video_id}_chunk_{chunk.chunk_index:04d}.txt"

        # Include metadata as a header comment — ingest_once.py passes it through
        content = (
            f"# source: {chunk.source}\n"
            f"# video_id: {chunk.video_id}\n"
            f"# video_title: {chunk.video_title}\n"
            f"# start_time: {chunk.start_time:.1f}s\n"
            f"# chunk_index: {chunk.chunk_index}\n\n"
            f"{chunk.text}"
        )

        filename.write_text(content, encoding="utf-8")
        saved += 1

    return saved


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def already_fetched(video_id: str) -> bool:
    """Check if this video has already been fetched and chunked."""
    existing = list(TRANSCRIPTS_DIR.glob(f"{video_id}_chunk_*.txt"))
    return len(existing) > 0


def process_video(video: VideoMeta, dry_run: bool = False) -> dict:
    """
    Full pipeline for a single video.
    Returns a status dict for the summary report.
    """
    status = {
        "video_id": video.video_id,
        "title": video.title,
        "status": None,
        "chunks": 0,
    }

    # Skip too-short videos
    if video.duration > 0 and video.duration < MIN_DURATION_SECONDS:
        logging.info(f"[skip] {video.video_id} — too short ({video.duration}s)")
        status["status"] = "skipped:too_short"
        return status

    # Skip already fetched
    if already_fetched(video.video_id):
        logging.info(f"[skip] {video.video_id} — already fetched")
        status["status"] = "skipped:already_fetched"
        return status

    if dry_run:
        status["status"] = "dry_run"
        return status

    # Fetch transcript
    segments = fetch_transcript(video)
    if segments is None:
        status["status"] = "skipped:no_transcript"
        return status

    # Cache raw transcript
    raw_cache = CACHE_DIR / f"{video.video_id}.json"
    raw_cache.write_text(json.dumps(segments, indent=2))

    # Clean
    cleaned = clean_transcript(segments)
    if not cleaned:
        status["status"] = "skipped:empty_after_cleaning"
        return status

    # Chunk
    chunks = chunk_transcript(video, cleaned)
    if not chunks:
        status["status"] = "skipped:no_chunks"
        return status

    # Save
    saved = save_chunks(chunks)
    status["status"] = "ok"
    status["chunks"] = saved

    time.sleep(0.5)   # be polite to YouTube's servers
    return status


def print_summary(results: list[dict]):
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    total_chunks = sum(r["chunks"] for r in results)
    skipped_short = sum(1 for r in results if r["status"] == "skipped:too_short")
    skipped_done = sum(1 for r in results if r["status"] == "skipped:already_fetched")
    skipped_no_transcript = sum(1 for r in results if r["status"] == "skipped:no_transcript")
    skipped_other = sum(1 for r in results
                        if r["status"] not in ("ok", "skipped:too_short",
                                               "skipped:already_fetched",
                                               "skipped:no_transcript", "dry_run"))

    print("\n" + "="*60)
    print("TRANSCRIPT FETCHER SUMMARY")
    print("="*60)
    print(f"  Total videos on channel:       {total}")
    print(f"  Transcripts fetched:           {ok}")
    print(f"  Total chunks saved:            {total_chunks}")
    print(f"  Skipped — already fetched:     {skipped_done}")
    print(f"  Skipped — no transcript:       {skipped_no_transcript}")
    print(f"  Skipped — too short:           {skipped_short}")
    print(f"  Skipped — other:               {skipped_other}")
    print("="*60)
    print(f"\nChunks saved to: {TRANSCRIPTS_DIR}")
    print(f"Run ingest_once.py to load into ChromaDB.\n")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Fetch and chunk Linbit YouTube transcripts for Ratgeber"
    )
    parser.add_argument(
        "--from-cache", action="store_true",
        help="Load channel video list from cache instead of re-fetching",
    )
    parser.add_argument(
        "--video-id", type=str, default=None,
        help="Process a single video ID only (for testing)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch video list only — do not download transcripts",
    )
    parser.add_argument(
        "--channel", type=str, default=CHANNEL_URL,
        help=f"YouTube channel URL (default: {CHANNEL_URL})",
    )
    args = parser.parse_args()

    # Step 1: Get video list
    if args.video_id:
        # Single video mode
        videos = [VideoMeta(
            video_id=args.video_id,
            title=args.video_id,
            duration=999,
            upload_date="unknown",
        )]
    else:
        videos = fetch_channel_videos(args.channel, from_cache=args.from_cache)

    if not videos:
        logging.error("No videos found — exiting")
        return

    logging.info(f"[main] processing {len(videos)} videos")

    # Step 2-5: Process each video
    results = []
    for i, video in enumerate(videos, 1):
        logging.info(f"[main] {i}/{len(videos)}: {video.title[:60]}")
        result = process_video(video, dry_run=args.dry_run)
        results.append(result)

    # Summary
    print_summary(results)


if __name__ == "__main__":
    main()
