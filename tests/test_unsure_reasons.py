"""Why an unsure or not-marked grade is unsure: one test per reason at its site, plus the shape checks.

Offline only. Uses the scripted FakeSolver and the part helpers from test_worksheet_shapes.py.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.ladder import Rungs  # noqa: E402
from core.solvers import AnswerSolver, CallBudget, Comparison, FakeSolver, JudgeReply, comparison_mark  # noqa: E402
from core.worksheet import grade_item  # noqa: E402
from core.worksheet_types import GRADE_LABELS, Grade, GradedItem, WorksheetItem, join_statement  # noqa: E402
from server.worksheet_api import (  # noqa: E402
    GRADES_SOURCE,
    RegradeRequest,
    grade_payload,
    load_grades,
    regrade_graded,
)
from test_worksheet_shapes import (  # noqa: E402
    CRITICAL,
    EXACT_INTEGRAL,
    FUNCTION_SETUP,
    INTEGRAL_THREE_OVER_X,
    _grade_one,
)

SKY = "Describe the shape of the graph."
UNREADABLE = r"\text{because it scatters}"
DIGEST = "a" * 64
BANK_TOPIC = "power_rule"


class _FixedSolver(AnswerSolver):
    """Answers every solve with one reply and every judge with one verdict. Never reaches the network."""

    name = "fixed"
    source = "fake"

    def __init__(self, reply: str, verdict: str = "unsure") -> None:
        self._reply = reply
        self._verdict = verdict

    def solve(self, statement: str, effort: str | None = None) -> str:
        return self._reply

    def judge(self, statement: str, student_answer: str, effort: str | None = None) -> JudgeReply:
        return JudgeReply(verdict=self._verdict)


def _part(statement: str, *answers: str, confidence: str = "high") -> WorksheetItem:
    return WorksheetItem(
        number=1,
        part_label="a",
        statement_latex=statement,
        student_answer_latex="; ".join(answers) or None,
        final_answers_latex=answers,
        explanation_text="",
        confidence=confidence,
    )


def _graded(item: WorksheetItem) -> GradedItem:
    return GradedItem(item=item, grade=grade_item(item, FakeSolver(), bank=()))


# ---------------------------------------------------------------------------
# reading: the low-confidence gate and a part with no answer
# ---------------------------------------------------------------------------


def test_reason_reading_low_confidence_part_is_not_marked_and_says_reading() -> None:
    grade = grade_item(_part(CRITICAL, "0", "2", confidence="low"), FakeSolver(), bank=())
    assert grade.method == "not_graded"
    assert grade.verdict == "unsure"
    assert grade.reason == "reading"


def test_reason_reading_part_with_no_answer_written_is_unsure_for_reading() -> None:
    grade = grade_item(_part(CRITICAL), FakeSolver(), bank=())
    assert grade.verdict == "unsure"
    assert grade.reason == "reading"


# ---------------------------------------------------------------------------
# format: an answer or an AI solve that SymPy cannot read
# ---------------------------------------------------------------------------


def test_reason_format_when_the_student_answer_is_not_readable_by_sympy() -> None:
    grade = grade_item(_part(SKY, UNREADABLE), _FixedSolver("2"), bank=())
    assert grade.verdict == "unsure"
    assert grade.reason == "format"


def test_reason_format_when_both_ai_solves_are_not_readable_by_sympy() -> None:
    grade = grade_item(_part(SKY, "2"), _FixedSolver(UNREADABLE), bank=())
    assert grade.verdict == "unsure"
    assert grade.reason == "format"


def test_reason_format_when_the_bank_key_cannot_be_compared_with_the_answer() -> None:
    problem = {"statement": SKY, "topic": BANK_TOPIC, "id": "T1", "answer": {"latex": "2"}}
    grade = grade_item(_part(SKY, UNREADABLE), FakeSolver(), bank=[problem])
    assert grade.method == "bank_key"
    assert grade.verdict == "unsure"
    assert grade.reason == "format"


# ---------------------------------------------------------------------------
# disagreement: an independent AI solve that parses and differs
# ---------------------------------------------------------------------------


def test_reason_disagreement_when_the_independent_ai_solve_differs_from_sympy() -> None:
    solver = FakeSolver({join_statement(FUNCTION_SETUP, CRITICAL): "x=0, x=3"})
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",), solver)
    assert grade.method == "sympy_computed"
    assert grade.verdict == "unsure"
    assert grade.reason == "disagreement"


def test_reason_disagreement_when_the_three_ai_solves_all_differ() -> None:
    rungs = Rungs(_FixedSolver("1"), _FixedSolver("2"), _FixedSolver("3"))
    grade = grade_item(_part(SKY, "5"), rungs, bank=())
    assert grade.method == "ai_ladder"
    assert grade.verdict == "unsure"
    assert grade.reason == "disagreement"


# ---------------------------------------------------------------------------
# no_verdict: a model call failed, was refused, or the judge gave no verdict
# ---------------------------------------------------------------------------


def test_reason_no_verdict_when_the_model_calls_fail() -> None:
    grade = grade_item(_part(SKY, "5"), FakeSolver(error="model down"), bank=())
    assert grade.verdict == "unsure"
    assert grade.reason == "no_verdict"


def test_reason_no_verdict_when_the_call_budget_is_spent() -> None:
    grade = grade_item(_part(SKY, "5"), FakeSolver(), bank=(), budget=CallBudget(0))
    assert grade.verdict == "unsure"
    assert grade.reason == "no_verdict"


# ---------------------------------------------------------------------------
# rule: a known rule fired, and its explanation names the fix
# ---------------------------------------------------------------------------


def test_reason_rule_for_a_missing_plus_c() -> None:
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln|x|",))
    assert grade.verdict == "unsure"
    assert grade.reason == "rule"


def test_reason_rule_for_a_domain_difference() -> None:
    grade = _grade_one(FUNCTION_SETUP, INTEGRAL_THREE_OVER_X, (r"3\ln x + C",))
    assert grade.verdict == "unsure"
    assert grade.reason == "rule"


def test_reason_rule_for_a_rounded_decimal_of_an_exact_answer() -> None:
    grade = _grade_one(FUNCTION_SETUP, EXACT_INTEGRAL, ("1.718",))
    assert grade.verdict == "unsure"
    assert grade.reason == "rule"


def test_reason_rule_for_a_constant_offset_and_a_domain_difference_in_the_comparison_helper() -> None:
    offset = comparison_mark(Comparison("unknown", 3, constant_offset=True), "x+1", "x", "sympy_computed", "s")
    domain = comparison_mark(Comparison("domain_differs", 3), "ln x", "ln|x|", "sympy_computed", "s")
    assert offset is not None and offset.reason == "rule"
    assert domain is not None and domain.reason == "rule"


# ---------------------------------------------------------------------------
# Correct and incorrect grades carry no reason
# ---------------------------------------------------------------------------


def test_reason_is_none_for_a_correct_sympy_mark() -> None:
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; 2",))
    assert grade.verdict == "correct"
    assert grade.reason is None


def test_reason_is_none_for_an_incorrect_sympy_mark() -> None:
    grade = _grade_one(FUNCTION_SETUP, CRITICAL, ("0; -2",))
    assert grade.verdict == "incorrect"
    assert grade.reason is None


def test_reason_is_none_for_an_agreed_ai_ladder_mark() -> None:
    grade = grade_item(_part(SKY, "5"), _FixedSolver("5"), bank=())
    assert grade.method == "ai_ladder"
    assert grade.verdict == "correct"
    assert grade.reason is None


# ---------------------------------------------------------------------------
# Shape: old saved grades load, and the server response carries the field
# ---------------------------------------------------------------------------


def test_reason_is_absent_from_an_old_saved_grade_and_the_file_still_loads(tmp_path: Path) -> None:
    grade = Grade(
        verdict="correct",
        method="sympy_computed",
        label=GRADE_LABELS["sympy_computed"],
        explanation="saved before the reason field existed",
    )
    old_grade = grade.model_dump(mode="json")
    old_grade.pop("reason")
    payload = {
        "source": GRADES_SOURCE,
        "saved_at": "2026-01-01T00:00:00+00:00",
        "reading_sha256": DIGEST,
        "graded": [
            {
                "item": _part(CRITICAL, "0", "2").model_dump(mode="json"),
                "grade": old_grade,
                "regraded": False,
                "changed_on_regrade": False,
            }
        ],
    }
    path = tmp_path / "grades_old.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_grades(path, DIGEST)
    assert loaded[0].grade.verdict == "correct"
    assert loaded[0].grade.reason is None


def test_reason_is_in_the_grade_response_and_survives_a_replay_regrade(tmp_path: Path) -> None:
    graded = _graded(_part(CRITICAL, "0", "2", confidence="low"))
    payload = grade_payload([graded], tmp_path)
    assert payload["graded"][0]["grade"]["reason"] == "reading"
    regraded = regrade_graded(RegradeRequest(graded=graded, mode="replay"))
    assert regraded["grade"]["reason"] == "reading"
    assert regraded["regraded"] is True
