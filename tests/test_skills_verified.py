"""Verified marks count only when the verdict is correct or incorrect (core/skills.py). Offline only."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.skills import build_profile, summarize  # noqa: E402
from core.worksheet_types import GRADE_LABELS, Grade, GradedItem, WorksheetItem  # noqa: E402

TOPIC = "algebraic"


def _graded(verdict: str, method: str, number: int = 1) -> GradedItem:
    item = WorksheetItem(
        number=number, statement_latex=f"problem {number}", student_answer_latex="x", topic_guess=TOPIC
    )
    grade = Grade(
        verdict=verdict,
        method=method,
        label=GRADE_LABELS[method],
        bank_topic=TOPIC if method == "bank_key" else None,
        bank_id="bank-1" if method == "bank_key" else None,
    )
    return GradedItem(item=item, grade=grade)


@pytest.mark.parametrize("method", ["bank_key", "sympy_computed"])
def test_unsure_mark_from_a_verified_method_is_not_verified(tmp_path, method: str) -> None:
    profile = build_profile([_graded("unsure", method)], tmp_path)
    skill = profile.skills[0]
    assert skill.verified_marks == 0
    assert skill.unsure == 1


@pytest.mark.parametrize("method", ["bank_key", "sympy_computed"])
@pytest.mark.parametrize("verdict", ["correct", "incorrect"])
def test_determinate_mark_from_a_verified_method_is_verified(tmp_path, method: str, verdict: str) -> None:
    profile = build_profile([_graded(verdict, method)], tmp_path)
    assert profile.skills[0].verified_marks == 1


def test_summary_does_not_count_an_unsure_verified_method_as_verified(tmp_path) -> None:
    items = [_graded("unsure", "bank_key", number=1), _graded("correct", "bank_key", number=2)]
    summary = summarize(build_profile(items, tmp_path))
    assert summary["verified_marks"] == 1
    assert summary["problems_seen"] == 2
