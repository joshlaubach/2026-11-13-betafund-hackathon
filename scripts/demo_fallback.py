"""Print bank fallback output for a few cases. Run as: python scripts/demo_fallback.py

Serves from the real bank with the repo's build/ folder as the gate folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.bank_fallback import (  # noqa: E402
    BUILD_DIR,
    describe_coverage,
    echo_checked_topics,
    serve,
)

CASES = (
    ("power_rule", 2),
    ("u_substitution", 2),
    ("no_such_topic", 2),
)
STATEMENT_WIDTH = 70
SEED = 0


def print_result(result: dict) -> None:
    print(f"{result['topic']} level {result['level']}: status={result['status']}")
    print(f"  label: {result['label']}")
    for problem in result["problems"]:
        statement = problem["statement"][:STATEMENT_WIDTH]
        print(f"  [{problem['id']} L{problem['level']}] {statement}")
        if "level_note" in problem:
            print(f"      level_note: {problem['level_note']}")
    print(f"  problems shown: {len(result['problems'])}")


def print_coverage(coverage: dict) -> None:
    print(
        "coverage: "
        f"topics_in_bank={coverage['topics_in_bank']} "
        f"topics_with_eligible={coverage['topics_with_eligible']} "
        f"echo_checked={coverage['echo_checked']} "
        f"eligible_problems={coverage['eligible_problems']}"
    )


def main() -> int:
    # Windows consoles may default to a code page that cannot print bank statements.
    sys.stdout.reconfigure(encoding="utf-8")
    gates = sorted(echo_checked_topics(BUILD_DIR))
    print(f"gate-enabled topics in {BUILD_DIR}: {gates if gates else 'none'}")
    for topic, level in CASES:
        print_result(serve(topic, level, seed=SEED, build_dir=BUILD_DIR))
    print_coverage(describe_coverage(BUILD_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
