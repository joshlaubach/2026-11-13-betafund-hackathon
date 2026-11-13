"""Demo: ask core.entry.request_problems for practice problems and print the result.

Modes: live (Anthropic API), replay (a saved run on disk), fake (scripted), bank (bank only).
Run as: python scripts/demo_entry.py --mode replay --topic power_rule --level 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.entry import MODES, STATUS_ERROR, request_problems  # noqa: E402

DEFAULT_TOPIC = "power_rule"
DEFAULT_LEVEL = 2
DEFAULT_MODE = "replay"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--level", type=int, default=DEFAULT_LEVEL)
    parser.add_argument("--mode", default=DEFAULT_MODE, help=" | ".join(MODES))
    return parser.parse_args()


def print_problem(index: int, problem: dict) -> None:
    print(f"PROBLEM {index}")
    print(f"  origin: {problem['origin']}")
    print(f"  label: {problem['label']}")
    print(f"  statement: {problem['statement']}")
    print(f"  answer: {problem['answer_latex']}")


def print_result(result: dict) -> None:
    print(f"status: {result['status']}")
    print(f"mode: requested={result['mode_requested']} used={result['mode_used']}")
    print(f"counts: {result['counts']}")
    for note in result["notes"]:
        print(f"note: {note}")
    for index, problem in enumerate(result["problems"], start=1):
        print_problem(index, problem)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    result = request_problems(args.topic, args.level, mode=args.mode)
    print_result(result)
    return 1 if result["status"] == STATUS_ERROR else 0


if __name__ == "__main__":
    sys.exit(main())
