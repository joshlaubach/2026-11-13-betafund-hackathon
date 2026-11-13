"""Tests for core/skills.py. Offline only: no model call, no network.

Every test passes an explicit temporary build_dir, so the real build/ folder never
changes the result.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import bank_fallback  # noqa: E402
from core.skills import (  # noqa: E402
    Profile,
    build_profile,
    recommend,
    summarize,
)
from core.worksheet_types import GRADE_LABELS, Grade, GradedItem, WorksheetItem  # noqa: E402

SOLID_TOPIC = "power_rule"
WEAK_TOPIC = "algebraic"
SHAKY_TOPIC = "chain_rule"
ONE_MARK_TOPIC = "implicit"
UNIT_LATER_TOPIC = "u_substitution"  # calc_i c4, earlier in the bank than by_parts
UNIT_EARLIER_TOPIC = "by_parts"  # calc_ii c6, later in the bank than u_substitution
TIE_FIRST = "chain_rule"
TIE_SECOND = "quotient_rule"  # both calc_i c2_derivatives
UNKNOWN_TOPIC = "not_a_bank_topic"


def graded(
    topic: str | None,
    verdict: str,
    method: str = "ai_judgment",
    number: int = 1,
    bank_topic: str | None = None,
) -> GradedItem:
    item = WorksheetItem(
        number=number,
        statement_latex=f"problem {number}",
        student_answer_latex="x",
        topic_guess=topic,
    )
    grade = Grade(
        verdict=verdict,
        method=method,
        label=GRADE_LABELS[method],
        bank_topic=bank_topic,
        bank_id="bank-1" if method == "bank_key" else None,
    )
    return GradedItem(item=item, grade=grade)


def skill_for(profile: Profile, topic: str):
    return next(skill for skill in profile.skills if skill.topic == topic)


@pytest.fixture
def build_dir(tmp_path):
    folder = tmp_path / "build"
    folder.mkdir()
    return folder


def write_gate(build_dir: Path, topic: str) -> None:
    payload = {
        "topic": topic,
        "enabled": True,
        "positive_failed": 0,
        "negative_failed": 0,
        "bank_sha256": bank_fallback.bank_sha256(),
    }
    (build_dir / f"gate_{topic}.json").write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# Status rules
# ---------------------------------------------------------------------------


def test_two_correct_and_no_incorrect_is_solid(build_dir):
    items = [graded(SOLID_TOPIC, "correct"), graded(SOLID_TOPIC, "correct", number=2)]
    assert skill_for(build_profile(items, build_dir), SOLID_TOPIC).status == "solid"


def test_single_correct_is_not_solid(build_dir):
    items = [graded(SOLID_TOPIC, "correct")]
    assert skill_for(build_profile(items, build_dir), SOLID_TOPIC).status == "not_enough_data"


def test_one_correct_and_one_unsure_is_not_solid(build_dir):
    items = [graded(SOLID_TOPIC, "correct"), graded(SOLID_TOPIC, "unsure", number=2)]
    assert skill_for(build_profile(items, build_dir), SOLID_TOPIC).status == "not_enough_data"


def test_correct_at_least_incorrect_with_some_wrong_is_shaky(build_dir):
    items = [graded(SHAKY_TOPIC, "correct"), graded(SHAKY_TOPIC, "incorrect", number=2)]
    assert skill_for(build_profile(items, build_dir), SHAKY_TOPIC).status == "shaky"


def test_more_incorrect_than_correct_is_weak(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect"),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(WEAK_TOPIC, "correct", number=3),
    ]
    assert skill_for(build_profile(items, build_dir), WEAK_TOPIC).status == "weak"


def test_zero_correct_two_incorrect_is_weak(build_dir):
    items = [graded(WEAK_TOPIC, "incorrect"), graded(WEAK_TOPIC, "incorrect", number=2)]
    assert skill_for(build_profile(items, build_dir), WEAK_TOPIC).status == "weak"


def test_single_incorrect_is_not_enough_data(build_dir):
    items = [graded(WEAK_TOPIC, "incorrect")]
    assert skill_for(build_profile(items, build_dir), WEAK_TOPIC).status == "not_enough_data"


def test_unsure_only_is_not_enough_data(build_dir):
    items = [
        graded(ONE_MARK_TOPIC, "unsure"),
        graded(ONE_MARK_TOPIC, "unsure", number=2),
        graded(ONE_MARK_TOPIC, "unsure", number=3),
    ]
    skill = skill_for(build_profile(items, build_dir), ONE_MARK_TOPIC)
    assert skill.status == "not_enough_data"
    assert (skill.correct, skill.incorrect, skill.unsure) == (0, 0, 3)


# ---------------------------------------------------------------------------
# Counts and placement
# ---------------------------------------------------------------------------


def test_verified_marks_count_bank_key_items_only(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect", method="bank_key", bank_topic=WEAK_TOPIC),
        graded(WEAK_TOPIC, "incorrect", number=2, method="ai_solve_sympy"),
        graded(WEAK_TOPIC, "correct", number=3, method="ai_judgment"),
    ]
    skill = skill_for(build_profile(items, build_dir), WEAK_TOPIC)
    assert skill.verified_marks == 1
    assert (skill.correct, skill.incorrect, skill.unsure) == (1, 2, 0)


def test_bank_key_topic_wins_over_topic_guess(build_dir):
    items = [
        graded("wrong_guess", "correct", method="bank_key", bank_topic=SOLID_TOPIC),
        graded(SOLID_TOPIC, "correct", number=2),
    ]
    profile = build_profile(items, build_dir)
    assert [skill.topic for skill in profile.skills] == [SOLID_TOPIC]
    assert skill_for(profile, SOLID_TOPIC).status == "solid"


def test_unplaced_items_are_counted_not_dropped(build_dir):
    items = [
        graded(None, "correct"),
        graded("", "incorrect", number=2),
        graded(WEAK_TOPIC, "incorrect", number=3),
    ]
    profile = build_profile(items, build_dir)
    assert profile.unplaced == 2
    assert [skill.topic for skill in profile.skills] == [WEAK_TOPIC]


def test_unknown_topic_is_kept_with_id_as_title(build_dir):
    items = [graded(UNKNOWN_TOPIC, "correct")]
    skill = skill_for(build_profile(items, build_dir), UNKNOWN_TOPIC)
    assert skill.title == UNKNOWN_TOPIC
    assert skill.course == "unknown"
    assert skill.unit == "unknown"


def test_bank_topic_gets_course_unit_and_title(build_dir):
    items = [graded(UNIT_LATER_TOPIC, "correct")]
    skill = skill_for(build_profile(items, build_dir), UNIT_LATER_TOPIC)
    assert skill.course == "calc_i"
    assert skill.unit == "c4_integration_basics"
    assert skill.title == "Substitution (indefinite and definite)"


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def test_weak_comes_before_shaky(build_dir):
    # The weak topic (chain_rule) sits later in the bank than the shaky one (algebraic),
    # so the status order, not the bank order, must decide.
    items = [
        graded(SHAKY_TOPIC, "incorrect"),
        graded(SHAKY_TOPIC, "incorrect", number=2),
        graded(WEAK_TOPIC, "correct"),
        graded(WEAK_TOPIC, "incorrect", number=2),
    ]
    profile = build_profile(items, build_dir)
    ranked = recommend(profile, count=2, build_dir=build_dir)
    assert [rec.topic for rec in ranked] == [SHAKY_TOPIC, WEAK_TOPIC]
    assert [rec.status for rec in ranked] == ["weak", "shaky"]


def test_earlier_unit_comes_first_within_same_status(build_dir):
    items = [
        graded(UNIT_EARLIER_TOPIC, "incorrect"),
        graded(UNIT_EARLIER_TOPIC, "incorrect", number=2),
        graded(UNIT_LATER_TOPIC, "incorrect"),
        graded(UNIT_LATER_TOPIC, "incorrect", number=2),
    ]
    ranked = recommend(build_profile(items, build_dir), build_dir=build_dir)
    assert [rec.topic for rec in ranked] == [UNIT_LATER_TOPIC, UNIT_EARLIER_TOPIC]


def test_ties_break_by_topic_id_regardless_of_input_order(build_dir):
    forward = [
        graded(TIE_FIRST, "incorrect"),
        graded(TIE_FIRST, "incorrect", number=2),
        graded(TIE_SECOND, "incorrect"),
        graded(TIE_SECOND, "incorrect", number=2),
    ]
    backward = list(reversed(forward))
    first = recommend(build_profile(forward, build_dir), build_dir=build_dir)
    second = recommend(build_profile(backward, build_dir), build_dir=build_dir)
    assert [rec.topic for rec in first] == [TIE_FIRST, TIE_SECOND]
    assert first == second


def test_solid_topics_are_skipped(build_dir):
    items = [
        graded(SOLID_TOPIC, "correct"),
        graded(SOLID_TOPIC, "correct", number=2),
        graded(ONE_MARK_TOPIC, "correct"),
    ]
    ranked = recommend(build_profile(items, build_dir), build_dir=build_dir)
    assert [rec.topic for rec in ranked] == [ONE_MARK_TOPIC]


def test_count_limits_the_list_and_ranks_start_at_one(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect"),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(SHAKY_TOPIC, "correct"),
        graded(SHAKY_TOPIC, "incorrect", number=2),
        graded(ONE_MARK_TOPIC, "correct"),
    ]
    ranked = recommend(build_profile(items, build_dir), count=2, build_dir=build_dir)
    assert [rec.rank for rec in ranked] == [1, 2]
    assert [rec.topic for rec in ranked] == [WEAK_TOPIC, SHAKY_TOPIC]


def test_suggested_levels_follow_status(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect"),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(SHAKY_TOPIC, "correct"),
        graded(SHAKY_TOPIC, "incorrect", number=2),
        graded(ONE_MARK_TOPIC, "correct"),
    ]
    levels = {
        rec.status: rec.suggested_level
        for rec in recommend(build_profile(items, build_dir), count=3, build_dir=build_dir)
    }
    assert levels == {"weak": 1, "shaky": 2, "not_enough_data": 2}


def test_reasons_cite_the_counts(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect", method="bank_key", bank_topic=WEAK_TOPIC),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(ONE_MARK_TOPIC, "correct"),
    ]
    ranked = recommend(build_profile(items, build_dir), count=3, build_dir=build_dir)
    by_topic = {rec.topic: rec.reason for rec in ranked}
    assert by_topic[WEAK_TOPIC] == "Got 0 of 2 problems right on this topic (1 verified mark)."
    assert by_topic[ONE_MARK_TOPIC] == (
        "Only 1 problem seen, so Echo cannot tell yet; try a few more."
    )


def test_echo_checked_only_with_valid_gate(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect"),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(SHAKY_TOPIC, "correct"),
        graded(SHAKY_TOPIC, "incorrect", number=2),
    ]
    profile = build_profile(items, build_dir)
    before = {rec.topic: rec.echo_checked for rec in recommend(profile, build_dir=build_dir)}
    assert before == {WEAK_TOPIC: False, SHAKY_TOPIC: False}

    write_gate(build_dir, WEAK_TOPIC)
    after = {rec.topic: rec.echo_checked for rec in recommend(profile, build_dir=build_dir)}
    assert after == {WEAK_TOPIC: True, SHAKY_TOPIC: False}


def test_non_positive_count_is_rejected(build_dir):
    with pytest.raises(ValueError):
        recommend(Profile(skills=(), unplaced=0), count=0, build_dir=build_dir)


def test_inputs_are_not_mutated(build_dir):
    items = [
        graded(WEAK_TOPIC, "incorrect", method="bank_key", bank_topic=WEAK_TOPIC),
        graded(WEAK_TOPIC, "correct", number=2),
        graded(None, "unsure", number=3),
    ]
    snapshot = [item.model_dump() for item in items]
    list_before = list(items)
    profile = build_profile(items, build_dir)
    recommend(profile, build_dir=build_dir)
    summarize(profile)
    assert items == list_before
    assert [item.model_dump() for item in items] == snapshot


def test_empty_input_gives_empty_results(build_dir):
    profile = build_profile([], build_dir)
    assert profile == Profile(skills=(), unplaced=0)
    assert recommend(profile, build_dir=build_dir) == []
    assert summarize(profile) == {
        "solid": 0,
        "shaky": 0,
        "weak": 0,
        "not_enough_data": 0,
        "problems_seen": 0,
        "verified_marks": 0,
        "ai_marks": 0,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_summary_counts_statuses_and_marks(build_dir):
    items = [
        graded(SOLID_TOPIC, "correct", method="bank_key", bank_topic=SOLID_TOPIC),
        graded(SOLID_TOPIC, "correct", number=2),
        graded(WEAK_TOPIC, "incorrect", method="bank_key", bank_topic=WEAK_TOPIC),
        graded(WEAK_TOPIC, "incorrect", number=2),
        graded(ONE_MARK_TOPIC, "correct", number=3),
        graded(None, "correct", number=4),
    ]
    summary = summarize(build_profile(items, build_dir))
    assert summary == {
        "solid": 1,
        "shaky": 0,
        "weak": 1,
        "not_enough_data": 1,
        "problems_seen": 5,
        "verified_marks": 2,
        "ai_marks": 3,
    }
