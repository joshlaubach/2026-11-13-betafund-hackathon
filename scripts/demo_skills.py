"""Print a skill profile, summary, and ranked recommendations for fixed fake graded items.

Run as: python scripts/demo_skills.py. Offline: no model call, no network.
Topics used: power_rule, algebraic, chain_rule, implicit (real bank ids).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.skills import (  # noqa: E402
    BUILD_DIR,
    build_profile,
    recommend,
    summarize,
)
from core.worksheet_types import (  # noqa: E402
    GRADE_LABELS,
    Grade,
    GradedItem,
    WorksheetItem,
)

DEMO_COUNT = 3
PROFILE_HEADER = f"{'topic':<14} {'status':<16} {'correct':>7} {'wrong':>5} {'unsure':>6} {'verified':>8}  course/unit"


def _graded(
    number: int,
    verdict: str,
    method: str,
    topic_guess: str | None,
    bank_topic: str | None = None,
) -> GradedItem:
    item = WorksheetItem(
        number=number,
        statement_latex=f"demo problem {number}",
        student_answer_latex="x",
        topic_guess=topic_guess,
    )
    grade = Grade(
        verdict=verdict,
        method=method,
        label=GRADE_LABELS[method],
        bank_topic=bank_topic,
        bank_id=f"demo-{number}" if method == "bank_key" else None,
    )
    return GradedItem(item=item, grade=grade)


def demo_items() -> list[GradedItem]:
    return [
        _graded(1, "correct", "bank_key", "power_rule", bank_topic="power_rule"),
        _graded(2, "correct", "ai_solve_sympy", "power_rule"),
        _graded(3, "incorrect", "bank_key", "algebraic", bank_topic="algebraic"),
        _graded(4, "incorrect", "ai_judgment", "algebraic"),
        _graded(5, "incorrect", "bank_key", "chain_rule", bank_topic="chain_rule"),
        _graded(6, "correct", "ai_judgment", "chain_rule"),
        _graded(7, "correct", "ai_solve_sympy", "implicit"),
    ]


def _profile_table(skills: tuple) -> list[str]:
    rows = [PROFILE_HEADER]
    for skill in skills:
        rows.append(
            f"{skill.topic:<14} {skill.status:<16} {skill.correct:>7} {skill.incorrect:>5} "
            f"{skill.unsure:>6} {skill.verified_marks:>8}  {skill.course}/{skill.unit}"
        )
    return rows


def main() -> int:
    profile = build_profile(demo_items(), build_dir=BUILD_DIR)
    print("Skill profile")
    for line in _profile_table(profile.skills):
        print(line)
    print(f"Unplaced items: {profile.unplaced}")

    summary = summarize(profile)
    print(
        "Summary: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )

    print("Recommendations")
    for rec in recommend(profile, count=DEMO_COUNT, build_dir=BUILD_DIR):
        print(
            f"{rec.rank}. {rec.topic} ({rec.status}, level {rec.suggested_level}, "
            f"echo_checked={rec.echo_checked}): {rec.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
