"""A writing instruction is stripped even when it mentions math; a second math ask is not."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.definitions import split_asks, without_writing_ask  # noqa: E402
from test_worksheet_shapes import _grade_one  # noqa: E402

DRONE_SETUP = (
    "A surveillance drone rises from the ground. Its upward velocity is modelled by the function "
    "v(t) = 1 - e^{-t} meters per second that is t seconds into its flight"
)
DRONE_STATEMENT = (
    "Compute $v(0)$. Write a complete sentence explaining the meaning of $v(0)$ in the context of the problem."
)


def test_writing_clause_mentioning_math_is_still_stripped():
    assert split_asks(DRONE_STATEMENT) == ("Compute v(0)",)
    assert "Write a complete sentence" not in without_writing_ask(DRONE_STATEMENT)


def test_drone_part_a_is_marked_by_sympy():
    grade = _grade_one(DRONE_SETUP, DRONE_STATEMENT, ("v(0) = 0",))
    assert grade.method == "sympy_computed"
    assert grade.verdict == "correct"


def test_second_math_ask_after_state_is_kept():
    statement = "Find f'(x) for f(x) = x^2 and state where f'(x) > 0."
    assert "where f'(x) > 0" in without_writing_ask(statement)


def test_writing_clause_with_a_second_ask_verb_is_kept():
    statement = "Write a sentence about v(0) and compute v'(2)."
    assert "compute" in without_writing_ask(statement).lower()
