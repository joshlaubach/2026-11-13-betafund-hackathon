"""Tests for multi-part worksheets: the shared setup, definitions, final answers, and SymPy sub-tasks.

Offline only: scripted reading sources and FakeSolvers, no network, no API key. SymPy runs in the
spawned child process, as in production.
"""

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.definitions import parse_definitions, split_asks  # noqa: E402
from core.solvers import FakeSolver  # noqa: E402
from core.sympy_task import (  # noqa: E402
    CROSS_CHECK_AGREES,
    ROUNDED_EXPLANATION,
    compute_answer,
    parse_task,
    parse_tasks,
    strip_label,
)
from core.worksheet import (  # noqa: E402
    STATUS_OK,
    FakeWorksheetSource,
    ReplayWorksheetSource,
    grade_item,
    grade_worksheet,
    load_worksheet_reading,
    read_worksheet,
)
from core.worksheet_types import (  # noqa: E402
    WorksheetItem,
    WorksheetReading,
    full_statement,
)

DRONE_CONTEXT = "A drone has velocity v(t) = 1 - e^{-t}."
PART_A = "Compute $v(0)$."
PART_B = "Compute $\\int_0^5 v(t)\\,dt$."
PART_C = "Find $v'(t)$. Compute $v'(0)$."
FULL_A = f"{DRONE_CONTEXT} {PART_A}"
FULL_B = f"{DRONE_CONTEXT} {PART_B}"
FULL_C = f"{DRONE_CONTEXT} {PART_C}"
EXACT_INTEGRAL = "4 + e^{-5}"
SENTENCE_SECRET = "SECRET WRITTEN SENTENCE"


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def make_png() -> bytes:
    """A valid 1x1 RGB PNG, so the image checks pass."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes([0, 255, 0, 0]))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", pixel) + _chunk(b"IEND", b"")


def _drone_reading() -> WorksheetReading:
    """The drone worksheet as the reader returns it: the setup once, and each part's own question."""
    return WorksheetReading(
        shared_context=DRONE_CONTEXT,
        items=(
            WorksheetItem(
                number=1, part_label="a", statement_latex=PART_A,
                student_answer_latex="v(0) = 0. The drone starts at rest.",
                final_answers_latex=("v(0) = 0",), explanation_text="The drone starts at rest.",
            ),
            WorksheetItem(
                number=2, part_label="b", statement_latex=PART_B,
                student_answer_latex="6 - e^{5}. The total distance is 6 - e^{5}.",
                final_answers_latex=("6 - e^{5}",), explanation_text="The total distance is 6 - e^{5}.",
            ),
            WorksheetItem(
                number=3, part_label="c", statement_latex=PART_C,
                student_answer_latex="v'(t) = e^{-t}, so v'(0) = 1.",
                final_answers_latex=("v'(t) = e^{-t}", "v'(0) = 1"),
                explanation_text="The acceleration starts at 1.",
            ),
        ),
    )


def _grade_drone(solver: FakeSolver, reading: WorksheetReading | None = None) -> list:
    """Read the scripted drone worksheet through the normal path, then grade every part with bank=()."""
    result = read_worksheet(make_png(), FakeWorksheetSource(reading or _drone_reading()), topics=())
    assert result["status"] == STATUS_OK
    graded_reading = WorksheetReading.model_validate(result["reading"])
    return grade_worksheet(graded_reading, solver, bank=())


def _part(statement: str, finals: tuple, context: str = DRONE_CONTEXT, working: str = "x") -> WorksheetItem:
    return WorksheetItem(
        number=1,
        statement_latex=statement,
        student_answer_latex=working,
        final_answers_latex=finals,
        context_latex=context,
    )


# ---------------------------------------------------------------------------
# The drone worksheet end to end
# ---------------------------------------------------------------------------


def test_drone_worksheet_marks_each_part_by_sympy() -> None:
    graded = _grade_drone(FakeSolver())
    grades = [entry.grade for entry in graded]
    assert [grade.verdict for grade in grades] == ["correct", "incorrect", "correct"]
    assert all(grade.method == "sympy_computed" for grade in grades)
    assert grades[1].reference_answer_latex == EXACT_INTEGRAL
    assert "6 - e^{5}" in grades[1].explanation


def test_part_c_names_each_sub_answer_with_the_sympy_value() -> None:
    base = _drone_reading()
    wrong_part_c = base.items[2].model_copy(update={"final_answers_latex": ("v'(t) = e^{-t}", "v'(0) = 2")})
    wrong_second = base.model_copy(update={"items": (base.items[0], base.items[1], wrong_part_c)})
    grades = [entry.grade for entry in _grade_drone(FakeSolver(), wrong_second)]
    assert grades[2].verdict == "incorrect"
    assert "v'(0): SymPy computes 1; the student wrote 2." in grades[2].explanation
    assert "v'(t): SymPy computes e^{- t}; the student wrote e^{-t}." in grades[2].explanation


def test_every_solve_call_receives_the_shared_setup() -> None:
    solver = FakeSolver()
    _grade_drone(solver)
    statements = [statement for statement, _effort in solver.solve_calls]
    assert statements == [FULL_A, FULL_B, FULL_C]  # one blind cross-check per part, with the setup
    assert all(statement.startswith(DRONE_CONTEXT) for statement in statements)
    assert solver.judge_calls == ()


def test_cross_check_agreement_is_recorded_per_part() -> None:
    solver = FakeSolver({FULL_A: "0", FULL_B: EXACT_INTEGRAL, FULL_C: "e^{-t}; 1"})
    grades = [entry.grade for entry in _grade_drone(solver)]
    assert all(CROSS_CHECK_AGREES in grade.explanation for grade in grades)


def test_explanation_text_is_never_sent_to_a_model() -> None:
    solver = FakeSolver()
    reading = _drone_reading()
    secret_item = reading.items[0].model_copy(update={"explanation_text": SENTENCE_SECRET})
    reading = reading.model_copy(update={"items": (secret_item,) + reading.items[1:]})
    graded = _grade_drone(solver, reading)
    assert SENTENCE_SECRET not in str(solver.solve_calls)
    assert SENTENCE_SECRET not in str(solver.judge_calls)
    assert SENTENCE_SECRET not in graded[0].grade.explanation


def test_the_shared_setup_is_copied_into_every_item() -> None:
    result = read_worksheet(make_png(), FakeWorksheetSource(_drone_reading()), topics=())
    items = result["reading"]["items"]
    assert result["reading"]["shared_context"] == DRONE_CONTEXT
    assert {item["context_latex"] for item in items} == {DRONE_CONTEXT}
    assert full_statement(WorksheetItem(**items[0])) == FULL_A


# ---------------------------------------------------------------------------
# Falling through to the AI ladder
# ---------------------------------------------------------------------------


def test_part_whose_setup_lacks_the_definition_falls_to_the_ladder() -> None:
    item = _part(PART_A, ("0",), context="", working="0")
    solver = FakeSolver({PART_A: "0"})
    grade = grade_item(item, solver, bank=())
    assert grade.method == "ai_ladder"
    assert grade.verdict == "correct"
    assert solver.solve_calls[0][0] == PART_A


def test_unsure_judge_mark_names_the_missing_definition() -> None:
    item = _part(PART_A, ("0",), context="", working="0")
    grade = grade_item(item, FakeSolver(verdict="unsure"), bank=())
    assert grade.method == "ai_judgment"
    assert grade.verdict == "unsure"
    assert "no shared setup defines v for this part" in grade.explanation


def test_mismatched_sub_answer_count_falls_through_to_the_ladder() -> None:
    item = _part(PART_C, ("v'(t) = e^{-t}",))
    grade = grade_item(item, FakeSolver({FULL_C: "e^{-t}"}, verdict="unsure"), bank=())
    assert grade.method == "ai_judgment"
    assert grade.method != "sympy_computed"


def test_integral_that_times_out_falls_through_to_the_ladder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sympy_task, "SYMPY_TIMEOUT_S", 1e-6)
    statement = "Compute $\\int_0^5 (1-e^{-t})\\,dt$."
    item = _part(statement, (EXACT_INTEGRAL,), context="", working=EXACT_INTEGRAL)
    grade = grade_item(item, FakeSolver({statement: EXACT_INTEGRAL}), bank=())
    assert grade.method == "ai_ladder"


def test_derivative_at_a_kink_falls_through() -> None:
    task = parse_task("Compute $v'(0)$.", "A drone has velocity v(t) = |t|.")
    assert task is not None
    assert compute_answer(task) is None


# ---------------------------------------------------------------------------
# SymPy tasks
# ---------------------------------------------------------------------------


def test_definite_integral_of_a_bare_expression_is_four_plus_e_to_minus_five() -> None:
    task = parse_task(r"Compute \int_0^5 (1-e^{-t}) dt.", "")
    value = compute_answer(task)
    assert value is not None
    assert sp.simplify(value - (4 + sp.exp(-5))) == 0


def test_writing_instructions_are_not_asks() -> None:
    assert split_asks("Compute $v(0)$ and write a sentence about it.") == ("Compute v(0)",)
    assert parse_tasks("Compute $v(0)$ and write a sentence.", DRONE_CONTEXT) is not None


def test_setup_definitions_are_parsed_by_shape() -> None:
    definitions = parse_definitions(DRONE_CONTEXT)
    assert set(definitions) == {"v"}
    assert definitions["v"].variable == "t"
    assert definitions["v"].body_latex == "1 - e^{-t}"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("v'(t) = e^{-t}", "e^{-t}"),
        ("v(0) = 0", "0"),
        ("v'(0) = 1", "1"),
        ("e^{-t}", "e^{-t}"),
    ],
)
def test_leading_labels_are_stripped(raw: str, expected: str) -> None:
    assert strip_label(raw) == expected


# ---------------------------------------------------------------------------
# Decimals and the not-graded explanation
# ---------------------------------------------------------------------------


def test_rounded_decimal_of_an_exact_constant_is_unsure() -> None:
    statement = "Compute $\\int_0^5 (1-e^{-t})\\,dt$."
    item = _part(statement, ("4.0067",), context="", working="4.0067")
    grade = grade_item(item, FakeSolver(), bank=())
    assert grade.verdict == "unsure"
    assert grade.method == "sympy_computed"
    assert grade.explanation == ROUNDED_EXPLANATION


def test_a_wrong_decimal_far_from_the_exact_value_is_incorrect() -> None:
    statement = "Compute $\\int_0^5 (1-e^{-t})\\,dt$."
    item = _part(statement, ("4.5",), context="", working="4.5")
    grade = grade_item(item, FakeSolver(), bank=())
    assert grade.verdict == "incorrect"
    assert grade.method == "sympy_computed"


# ---------------------------------------------------------------------------
# Old saved readings
# ---------------------------------------------------------------------------


def test_old_saved_reading_without_new_fields_still_loads(tmp_path: Path) -> None:
    png = make_png()
    payload = {
        "source": "fake",
        "saved_at": "2026-01-01T00:00:00+00:00",
        "image_sha256": hashlib.sha256(png).hexdigest(),
        "reading": {
            "items": [
                {
                    "number": 1,
                    "statement_latex": "Find $f'(x)$ for $f(x) = 3x^{4}$.",
                    "student_answer_latex": "12x^{3}",
                    "topic_guess": "power_rule",
                    "confidence": "high",
                    "notes": "",
                }
            ],
            "notes": "old",
        },
    }
    path = tmp_path / "old.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    saved = load_worksheet_reading(path)
    item = saved["reading"].items[0]
    assert item.context_latex == ""
    assert item.final_answers_latex == ()
    assert item.part_label is None
    assert item.explanation_text == ""
    assert saved["reading"].shared_context == ""
    result = read_worksheet(png, ReplayWorksheetSource(path), topics=["power_rule"])
    assert result["status"] == STATUS_OK


def test_definition_body_is_cut_at_the_first_plain_word() -> None:
    from core.definitions import parse_definitions

    setup = "Its velocity is modelled by v(t) = 1 - e^{-t} meters per second that is t seconds into its flight"
    definitions = parse_definitions(setup)
    assert definitions["v"].body_latex == "1 - e^{-t}"


def test_models_never_see_a_request_to_write_a_sentence() -> None:
    from core.solvers import Question

    question = Question(
        "(c) Find v'(t). Compute v'(0) and write a sentence to interpret its meaning in the context of the problem.",
        "v(t) = 1 - e^{-t}",
        ("e^{-t}", "1"),
        "v'(t) = e^{-t}",
    )
    assert "sentence" not in question.full
    assert "Compute v'(0)" in question.full
