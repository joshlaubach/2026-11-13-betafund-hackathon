"""Replay grading never starts SymPy, and a failed item is logged. Offline only: no model, no network."""

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from core import sympy_task  # noqa: E402
from core.bank_fallback import BANK_PATH  # noqa: E402
from core.solvers import FakeSolver  # noqa: E402
from core.worksheet_types import WorksheetItem, WorksheetReading  # noqa: E402
from scripts.audit_bank import classify, load_bank  # noqa: E402
from server import worksheet_api  # noqa: E402

LA01 = next(problem for problem in load_bank(BANK_PATH) if problem["id"] == "LA01")
LA01_STATEMENT = LA01["statement"]
DERIVATIVE = "Find $f'(x)$ for $f(x) = 5x^{7} - 3x^{2} + 11$."
DERIVATIVE_ANSWER = "35x^{6} - 6x"


def _item(statement: str, student: str | None, number: int = 1, topic: str | None = None) -> WorksheetItem:
    return WorksheetItem(
        number=number, statement_latex=statement, student_answer_latex=student, topic_guess=topic
    )


def _problems() -> tuple[dict, ...]:
    return tuple(problem for problem in load_bank(BANK_PATH) if classify(problem) is None)


@pytest.fixture
def computations(monkeypatch) -> list:
    """Records every attempt to start a SymPy computation. Each attempt raises."""
    attempts: list = []

    def refuse(task: object) -> None:
        attempts.append(task)
        raise AssertionError("replay must not start a SymPy computation")

    monkeypatch.setattr(sympy_task, "compute_answer", refuse)
    return attempts


def test_replay_grades_a_bank_match_without_a_sympy_computation(computations) -> None:
    graded = worksheet_api._replay_item(
        _item(LA01_STATEMENT, "-\\frac{1}{8}", topic="algebraic"), _problems()
    )
    assert graded.grade.method == "bank_key"
    assert graded.grade.verdict == "correct"
    assert computations == []


def test_replay_marks_a_derivative_unsure_without_computing_it(computations) -> None:
    graded = worksheet_api._replay_item(_item(DERIVATIVE, DERIVATIVE_ANSWER), _problems())
    assert graded.grade.verdict == "unsure"
    assert graded.grade.explanation == worksheet_api.NO_SAVED_GRADE_EXPLANATION
    assert computations == []


def test_replay_request_grades_every_item_without_a_sympy_computation(
    computations, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(worksheet_api, "_saved_grades", lambda digest: None)
    reading = WorksheetReading(
        items=(
            _item(LA01_STATEMENT, "-\\frac{1}{8}", topic="algebraic"),
            _item(DERIVATIVE, DERIVATIVE_ANSWER, number=2),
        )
    )
    payload = worksheet_api.grade_reading(worksheet_api.GradeRequest(reading=reading, mode="replay"), tmp_path)
    assert [entry["grade"]["method"] for entry in payload["graded"]] == ["bank_key", "ai_judgment"]
    assert computations == []


def test_item_failure_is_logged_with_a_traceback_and_gives_unsure(monkeypatch, caplog) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("scripted grading fault")

    monkeypatch.setattr(worksheet_api, "grade_item", broken)
    with caplog.at_level(logging.ERROR, logger="server.worksheet_api"):
        graded = worksheet_api._grade_one(_item(DERIVATIVE, "x"), FakeSolver(), _problems())
    assert graded.grade.verdict == "unsure"
    assert graded.grade.explanation == worksheet_api.UNGRADED_EXPLANATION
    records = [record for record in caplog.records if record.name == "server.worksheet_api"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is not None
