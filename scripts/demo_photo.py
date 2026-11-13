"""Demo: read a photo of a calculus problem into a reading a tutor confirms.

Modes: live (Anthropic vision), replay (a saved reading on disk), fake (scripted, no model).
Default mode comes from ECHO_MODE in .env, else fake. Nothing is used until a tutor confirms it.
Run as: python scripts/demo_photo.py --mode fake --image photo.png
Exit codes: 0 ok, 1 error or unreadable, 2 bad arguments.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.drafter import DEFAULT_EFFORT, DEFAULT_MODEL, SOURCE_FAKE  # noqa: E402
from core.photo_reader import (  # noqa: E402
    STATUS_OK,
    FakePhotoSource,
    LivePhotoSource,
    PhotoReading,
    PhotoSource,
    ReplayPhotoSource,
    read_photo,
    save_reading,
)

MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODES = (MODE_LIVE, MODE_REPLAY, SOURCE_FAKE)
ENV_MODE = "ECHO_MODE"
ENV_MODEL = "ANTHROPIC_MODEL"
ENV_EFFORT = "ANTHROPIC_EFFORT"
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_ARGS = 2


def load_image(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError as error:
        print(f"could not read image {path}: {error}")
        return None


def build_source(mode: str, replay_path: Path | None) -> PhotoSource:
    """Raises OSError or ValueError when a saved reading cannot be opened."""
    if mode == MODE_LIVE:
        return LivePhotoSource(os.environ.get(ENV_MODEL, DEFAULT_MODEL), os.environ.get(ENV_EFFORT, DEFAULT_EFFORT))
    if mode == MODE_REPLAY:
        return ReplayPhotoSource(replay_path)
    return FakePhotoSource()


def source_line(source: PhotoSource) -> str:
    if isinstance(source, LivePhotoSource):
        return f"source: LIVE ({source.model}, effort {source.effort})"
    if isinstance(source, ReplayPhotoSource):
        return f"source: REPLAY of a {source.source.upper()} reading (saved {source.saved_at})"
    return "source: FAKE (scripted reading, no model call)"


def print_reading(reading: dict) -> None:
    print(f"problem_latex: {reading['problem_latex']}")
    print(f"topic_guess: {reading['topic_guess']}")
    print(f"confidence: {reading['confidence']}")
    print(f"notes: {reading['notes']}")


def print_result(source: PhotoSource, result: dict) -> None:
    print(source_line(source))
    print(f"status: {result['status']}")
    if result["reading"] is not None:
        print_reading(result["reading"])
    print(f"topic_guess_valid: {result['topic_guess_valid']}")
    print(f"checker_readable: {result['checker_readable']}")
    if result["checker_reason"] is not None:
        print(f"checker_reason: {result['checker_reason']}")
    print(f"image_sha256: {result['image_sha256']}")
    if result["tokens"] is not None:
        print(f"tokens: {result['tokens']}")
    if result["error"] is not None:
        print(f"error: {result['error']}")


def parse_args(default_mode: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", type=Path, required=True, help="PNG, JPEG, WEBP, or GIF photo")
    parser.add_argument("--mode", default=default_mode, help="live | replay | fake")
    parser.add_argument("--save", type=Path, default=None, help="save the reading as a replay, only if status is ok")
    parser.add_argument("--replay", type=Path, default=None, help="saved reading to play back in replay mode")
    return parser.parse_args()


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    default_mode = os.environ.get(ENV_MODE, "").strip().lower() or SOURCE_FAKE
    args = parse_args(default_mode)
    if args.mode not in MODES:
        print(f"unknown mode {args.mode!r}; use one of {MODES}")
        return EXIT_BAD_ARGS
    if args.mode == MODE_REPLAY and args.replay is None:
        print("replay mode needs --replay PATH")
        return EXIT_BAD_ARGS
    image = load_image(args.image)
    if image is None:
        return EXIT_BAD_ARGS
    try:
        source = build_source(args.mode, args.replay)
    except (OSError, ValueError) as error:
        print(f"could not open the saved reading: {error}")
        return EXIT_BAD_ARGS
    result = read_photo(image, source)
    print_result(source, result)
    if result["status"] != STATUS_OK:
        return EXIT_FAILED
    if args.save is not None:
        reading = PhotoReading.model_validate(result["reading"])
        try:
            save_reading(args.save, result["image_sha256"], reading, source.source)
        except (OSError, ValueError) as error:
            print(f"could not save the reading: {error}")
            return EXIT_FAILED
        print(f"saved reading to {args.save}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
