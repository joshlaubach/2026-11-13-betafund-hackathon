"""Demo: read a worksheet photo into problems and grade each written answer.

Modes: live (Anthropic vision and solver), replay (a saved reading on disk; the solver
makes no network call), fake (scripted reading, no model). Default mode comes from ECHO_MODE
in .env, else fake. Every mark is labeled with how it was made.
Run as: python scripts/demo_worksheet.py --mode fake --image worksheet.png
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
from core.worksheet import (  # noqa: E402
    STATUS_OK,
    AnswerSolver,
    FakeSolver,
    FakeWorksheetSource,
    LiveSolver,
    LiveWorksheetSource,
    ReplayWorksheetSource,
    WorksheetSource,
    grade_worksheet,
    read_worksheet,
    save_worksheet_reading,
)
from core.worksheet_types import (  # noqa: E402
    GRADE_DISCLAIMER,
    GradedItem,
    WorksheetReading,
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


def build_source(mode: str, replay_path: Path | None) -> WorksheetSource:
    """Raises OSError or ValueError when a saved reading cannot be opened."""
    if mode == MODE_LIVE:
        model = os.environ.get(ENV_MODEL, DEFAULT_MODEL)
        return LiveWorksheetSource(model, os.environ.get(ENV_EFFORT, DEFAULT_EFFORT))
    if mode == MODE_REPLAY:
        return ReplayWorksheetSource(replay_path)
    return FakeWorksheetSource()


def build_solver(mode: str) -> AnswerSolver:
    """Only live mode may reach the network for grading."""
    if mode == MODE_LIVE:
        return LiveSolver(os.environ.get(ENV_MODEL, DEFAULT_MODEL), os.environ.get(ENV_EFFORT, DEFAULT_EFFORT))
    return FakeSolver()


def source_line(source: WorksheetSource, solver: AnswerSolver) -> str:
    if isinstance(source, LiveWorksheetSource):
        reading = f"source: LIVE ({source.model}, effort {source.effort})"
    elif isinstance(source, ReplayWorksheetSource):
        reading = f"source: REPLAY of a {source.source.upper()} reading (saved {source.saved_at})"
    else:
        reading = "source: FAKE (scripted reading, no model call)"
    grading = "grading: LIVE solver" if isinstance(solver, LiveSolver) else "grading: FAKE solver (no model call)"
    return f"{reading}; {grading}"


def print_item(graded: GradedItem) -> None:
    item = graded.item
    grade = graded.grade
    print(f"{item.number}. {item.statement_latex}")
    print(f"   student answer: {item.student_answer_latex if item.student_answer_latex else '(none written)'}")
    print(f"   topic guess: {item.topic_guess}")
    print(f"   verdict: {grade.verdict}")
    print(f"   label: {grade.label}")
    print(f"   explanation: {grade.explanation}")
    if grade.reference_answer_latex is not None:
        print(f"   reference answer: {grade.reference_answer_latex}")


def print_failure(result: dict) -> None:
    if result["reading"] is not None:
        print(f"notes: {result['reading']['notes']}")
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
    solver = build_solver(args.mode)
    print(source_line(source, solver))
    result = read_worksheet(image, source)
    print(f"status: {result['status']}")
    print(f"image_sha256: {result['image_sha256']}")
    if result["status"] != STATUS_OK:
        print_failure(result)
        return EXIT_FAILED
    reading = WorksheetReading.model_validate(result["reading"])
    if reading.notes:
        print(f"notes: {reading.notes}")
    for graded in grade_worksheet(reading, solver):
        print_item(graded)
    print(GRADE_DISCLAIMER)
    if args.save is not None:
        try:
            save_worksheet_reading(args.save, result["image_sha256"], reading, source.source)
        except (OSError, ValueError) as error:
            print(f"could not save the reading: {error}")
            return EXIT_FAILED
        print(f"saved reading to {args.save}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
