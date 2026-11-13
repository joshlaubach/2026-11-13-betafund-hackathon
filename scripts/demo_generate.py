"""Demo: draft power_rule problems and keep only the ones the checker accepts.

Modes: live (Anthropic API), replay (a saved run on disk), fake (scripted, no model).
Default mode comes from ECHO_MODE in .env, else fake.
Run as: python scripts/demo_generate.py --mode fake --save replay/power_rule_L2_fake.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.bank_fallback import BUILD_DIR, echo_checked_topics  # noqa: E402
from core.drafter import (  # noqa: E402
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    SOURCE_FAKE,
    SOURCE_LIVE,
    TOPIC,
    Draft,
    DraftSource,
    FakeSource,
    LiveSource,
    ReplaySource,
    generate,
    save_run,
)

GATE_FILE = BUILD_DIR / "gate_power_rule.json"
MODES = ("live", "replay", "fake")
DEFAULT_LEVEL = 2
DEFAULT_REPLAY = REPO_ROOT / "replay" / "power_rule_L2.json"
N_DRAFTS = 6  # the fake batch holds 6 drafts; every mode asks for the same number
COUNT = 3
SAMPLE_WIDTH = 6

FAKE_DRAFTS = [
    Draft(function_latex="3x^{4} + 2x", evaluate_at=None, key_latex="12 x^{3} + 2"),
    Draft(function_latex="5x^{3} - x", evaluate_at=None, key_latex="15 x^{2}"),
    Draft(
        function_latex="\\sqrt{x} + 4x^{3}",
        evaluate_at=None,
        key_latex="\\frac{1}{2 \\sqrt{x}} + 12 x^{2}",
    ),
    Draft(function_latex="3x^{4}   +  2x", evaluate_at=None, key_latex="12 x^{3} + 2"),
    Draft(function_latex="2x^{5} - 7x^{2} + 1", evaluate_at=None, key_latex="10x^{4} + 14x"),
    Draft(function_latex="x^{3} - 4x", evaluate_at="2", key_latex="8"),
]


def check_gate() -> int | None:
    """Return an exit code when the power_rule gate is missing or not trusted, else None."""
    if not GATE_FILE.exists():
        print(f"no gate file at {GATE_FILE}; run python scripts/gate_power_rule.py first")
        return 2
    if TOPIC not in echo_checked_topics(BUILD_DIR):
        print("gate file is disabled or out of date with the bank; rerun python scripts/gate_power_rule.py")
        return 2
    return None


def source_line(mode: str, source: DraftSource) -> str:
    if mode == "live":
        return f"source: LIVE ({source.name})"
    if mode == "replay":
        return f"source: REPLAY of a {source.source.upper()} run (saved {source.saved_at})"
    return "source: FAKE (scripted drafts, no model call)"


def print_accepted(index: int, item: dict) -> None:
    print(f"ACCEPTED {index}")
    print(f"  statement: {item['statement']}")
    print(f"  key: {item['key_latex']}")
    print(f"  label: {item['label']}")
    checker = item["checker"]
    print(f"  checker: outcome={checker['outcome']}; {checker['reason']}")
    print(f"  derivative computed by SymPy: {checker['true_answer']}")
    for x_value, true_value, key_value in checker["samples"]:
        print(f"    x = {x_value:g}: checker {true_value:.{SAMPLE_WIDTH}g}, key {key_value:.{SAMPLE_WIDTH}g}")


def print_rejected(index: int, item: dict) -> None:
    print(f"REJECTED {index}")
    print(f"  statement: {item['statement']}")
    print(f"  key: {item['key_latex']}")
    print(f"  outcome: {item['outcome']}")
    print(f"  reason: {item['reason']}")


def print_result(mode: str, source: DraftSource, result: dict, level: int) -> None:
    print(source_line(mode, source))
    print(
        f"{TOPIC} level {level}: status={result['status']} drafted={result['drafted']} "
        f"accepted={len(result['accepted'])} rejected={len(result['rejected'])} "
        f"duplicates={len(result['duplicates'])} shortfall={result['shortfall']}"
    )
    for index, item in enumerate(result["accepted"], start=1):
        print_accepted(index, item)
    for index, item in enumerate(result["rejected"], start=1):
        print_rejected(index, item)
    for function in result["duplicates"]:
        print(f"DUPLICATE skipped (same function as an earlier draft): {function}")
    print(f"shortfall: {result['shortfall']} (needs {COUNT} accepted)")


def build_source(mode: str, replay_path: Path) -> DraftSource:
    if mode == "live":
        return LiveSource(
            os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
            os.environ.get("ANTHROPIC_EFFORT", DEFAULT_EFFORT),
        )
    if mode == "replay":
        return ReplaySource(replay_path)
    return FakeSource(FAKE_DRAFTS)


def parse_args(default_mode: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", default=default_mode, help="live | replay | fake")
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--level", type=int, default=DEFAULT_LEVEL)
    parser.add_argument("--save", type=Path, default=None, help="save the drafts as a replay run")
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    return parser.parse_args()


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    default_mode = os.environ.get("ECHO_MODE", "").strip().lower() or SOURCE_FAKE
    args = parse_args(default_mode)
    if args.mode not in MODES:
        print(f"unknown mode {args.mode!r}; use one of {MODES}")
        return 2
    gate_exit = check_gate()
    if gate_exit is not None:
        return gate_exit
    try:
        source = build_source(args.mode, args.replay)
    except (OSError, ValueError) as error:
        print(f"could not open the replay run: {error}")
        return 2
    result = generate(args.topic, args.level, source, count=COUNT, n_drafts=N_DRAFTS)
    print_result(args.mode, source, result, args.level)
    if result["status"] != "ok":
        print(f"error: {result['error']}")
        return 1
    if args.save is not None:
        drafts = [Draft.model_validate(item) for item in result["drafts"]]
        save_run(args.save, args.topic, args.level, drafts, source.source)
        print(f"saved {len(drafts)} drafts to {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
