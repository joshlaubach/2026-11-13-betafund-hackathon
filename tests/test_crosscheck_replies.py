"""The blind AI cross-check reads replies in the shapes a model writes: chains, labels, point lists, and prose.

Offline only: scripted FakeSolvers and the shared worksheet helpers, no network, no API key. A reply can
confirm a SymPy mark or make it unsure. A reply that cannot be read leaves the SymPy mark as computed.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.solvers import FakeSolver  # noqa: E402
from core.worksheet_types import join_statement  # noqa: E402
from test_worksheet_shapes import _grade_one  # noqa: E402

UNPARSABLE_NOTE = sympy_task.UNPARSABLE_CROSS_CHECK
CROSS_CHECK_AGREES = sympy_task.CROSS_CHECK_AGREES
DRONE_CONTEXT = "A drone has velocity v(t) = 1 - e^{-t}."
VALUE_AT_ZERO = "Compute $v(0)$."
CURVE_SETUP = "Suppose we have an implicitly defined curve given by: y^2 = x^3 - 3x + 3"
HORIZONTAL = r"Find the coordinates of all points on the curve where the tangent line is horizontal."
TRUE_POINTS = r"(1,1),(1,-1),(-1,\sqrt{5}),(-1,-\sqrt{5})"


def _ai(setup: str, statement: str, reply: str) -> FakeSolver:
    """A FakeSolver whose blind solve of this part returns reply."""
    return FakeSolver({join_statement(setup, statement): reply})


# ---------------------------------------------------------------------------
# Case 1: chains "A=B=C" and "x=2" are compared by their last segment
# ---------------------------------------------------------------------------


def test_crosscheck_chain_last_segment_confirms_a_correct_value() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=1-e^{0}=0")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_chain_keeps_an_incorrect_value_incorrect_and_confirms_sympy() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=1-e^{0}=0")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("1",), solver)
    assert grade.verdict == "incorrect"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_chain_with_a_differing_last_segment_makes_a_correct_mark_unsure() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=1-e^{0}=1")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "unsure"
    assert "may have been read wrongly" in grade.explanation


def test_crosscheck_chain_falls_back_to_an_earlier_segment_when_the_last_does_not_read() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=1-e^{0}=the value at zero")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "correct"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_chain_label_only_reply_is_read_as_its_value() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=0")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "correct"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_chain_x_equals_value_reply_takes_the_right_side() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "x=0")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "correct"
    assert CROSS_CHECK_AGREES in grade.explanation


# ---------------------------------------------------------------------------
# Case 2: point lists with LaTeX spacing are compared as sets of points
# ---------------------------------------------------------------------------


def test_crosscheck_points_spaced_list_confirms_a_correct_set() -> None:
    solver = _ai(CURVE_SETUP, HORIZONTAL, r"(1,1),\ (1,-1),\ (-1,\sqrt{5}),\ (-1,-\sqrt{5})")
    grade = _grade_one(CURVE_SETUP, HORIZONTAL, (TRUE_POINTS,), solver)
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_points_spaced_list_keeps_an_incorrect_set_incorrect() -> None:
    solver = _ai(CURVE_SETUP, HORIZONTAL, r"(1,1),\ (1,-1),\ (-1,\sqrt{5}),\ (-1,-\sqrt{5})")
    grade = _grade_one(CURVE_SETUP, HORIZONTAL, ("(-1,0),(1,0)",), solver)
    assert grade.verdict == "incorrect"
    assert CROSS_CHECK_AGREES in grade.explanation


def test_crosscheck_points_partial_list_is_a_genuine_disagreement_and_unsure() -> None:
    solver = _ai(CURVE_SETUP, HORIZONTAL, r"(1,1),\ (1,-1)")
    grade = _grade_one(CURVE_SETUP, HORIZONTAL, (TRUE_POINTS,), solver)
    assert grade.verdict == "unsure"
    assert "may have been read wrongly" in grade.explanation


# ---------------------------------------------------------------------------
# Case 3: a reply that cannot be parsed at all keeps the SymPy mark, with a note
# ---------------------------------------------------------------------------


def test_crosscheck_unparsable_reply_keeps_a_correct_value_correct_with_the_note() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "the answer is zero, obviously")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert UNPARSABLE_NOTE in grade.explanation
    assert "may have been read wrongly" not in grade.explanation


def test_crosscheck_unparsable_reply_keeps_an_incorrect_value_incorrect_with_the_note() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "the answer is zero, obviously")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("1",), solver)
    assert grade.verdict == "incorrect"
    assert grade.method == "sympy_computed"
    assert UNPARSABLE_NOTE in grade.explanation


def test_crosscheck_unparsable_points_reply_keeps_a_correct_set_correct_with_the_note() -> None:
    solver = _ai(CURVE_SETUP, HORIZONTAL, "the points are nice")
    grade = _grade_one(CURVE_SETUP, HORIZONTAL, (TRUE_POINTS,), solver)
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert UNPARSABLE_NOTE in grade.explanation


def test_crosscheck_unparsable_reply_never_makes_a_wrong_answer_correct() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "the answer is zero, obviously")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("5",), solver)
    assert grade.verdict == "incorrect"


def test_crosscheck_differing_parsed_reply_still_makes_a_correct_mark_unsure() -> None:
    solver = _ai(DRONE_CONTEXT, VALUE_AT_ZERO, "v(0)=1")
    grade = _grade_one(DRONE_CONTEXT, VALUE_AT_ZERO, ("0",), solver)
    assert grade.verdict == "unsure"
    assert "may have been read wrongly" in grade.explanation
    assert UNPARSABLE_NOTE not in grade.explanation
