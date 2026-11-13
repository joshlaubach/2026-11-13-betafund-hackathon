"""Tests for core/practice.py: bank steps and the SymPy answer check. Offline; no model call.

check_answer runs SymPy in a spawned child process, so each check takes a few seconds on Windows.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import practice  # noqa: E402
from scripts.audit_bank import classify, load_bank  # noqa: E402
from core.bank_fallback import BANK_PATH  # noqa: E402

LA_TOPIC = "algebraic"
LA_ID = "LA01"
LA_ANSWER = r"- \frac{1}{8}"  # bank answer -1/8
CR_TOPIC = "chain_rule"
CR_ID = "CR47"
CR_ANSWER = r"\frac{x}{\sqrt{x^{2} + 3}}"
DQ_TOPIC = "difference_quotient"
DQ_ID = "DQ01"  # its answer uses the variable h, which the reader does not accept
REFERENCE = r"x^{2} + 1"
EVIDENCE_TEN_POINTS = "compared at 10 sample points by numeric evaluation"
NO_EVIDENCE = "no comparison was made"
BANK_KEY_SUBJECT = "the verified answer for this problem"
OWN_KEY_PHRASE = "the problem's own key as shown on the page"


def _bank_problem(topic: str, problem_id: str) -> dict:
    for problem in load_bank(BANK_PATH):
        if problem["topic"] == topic and str(problem["id"]) == problem_id:
            return problem
    raise AssertionError(f"bank has no problem {topic}/{problem_id}")


def _an_ineligible_key() -> tuple[str, str]:
    for problem in load_bank(BANK_PATH):
        if classify(problem) is not None:
            return problem["topic"], str(problem["id"])
    raise AssertionError("bank has no ineligible problem to test")


# ---------- get_steps ----------


def test_get_steps_returns_verified_steps_and_answer_for_an_eligible_problem():
    # Arrange
    expected_steps = _bank_problem(LA_TOPIC, LA_ID)["steps"]

    # Act
    result = practice.get_steps(LA_TOPIC, LA_ID)

    # Assert
    assert result["status"] == "ok"
    assert result["topic"] == LA_TOPIC
    assert result["problem_id"] == LA_ID
    assert result["steps"] == expected_steps
    assert result["answer_latex"] == LA_ANSWER
    assert result["source"] == "bank"


def test_get_steps_returns_every_step_as_a_string():
    result = practice.get_steps(CR_TOPIC, CR_ID)

    assert result["status"] == "ok"
    assert result["steps"] and all(isinstance(step, str) for step in result["steps"])


def test_get_steps_unknown_id_is_an_error():
    result = practice.get_steps(LA_TOPIC, "NOPE99")

    assert result["status"] == "error"
    assert "error" in result and "steps" not in result


def test_get_steps_wrong_topic_for_a_real_id_is_an_error():
    result = practice.get_steps("chain_rule", LA_ID)

    assert result["status"] == "error"


def test_get_steps_ineligible_problem_is_an_error():
    topic, problem_id = _an_ineligible_key()

    result = practice.get_steps(topic, problem_id)

    assert result["status"] == "error"
    assert "steps" not in result


@pytest.mark.parametrize(
    "topic, problem_id",
    [
        ("", LA_ID),
        (LA_TOPIC, ""),
        ("algebraic topic", LA_ID),
        (LA_TOPIC, "LA01; drop"),
        ("x" * 81, LA_ID),
        (LA_TOPIC, "y" * 81),
        (LA_TOPIC, "../LA01"),
        (None, LA_ID),
        (LA_TOPIC, 1),
    ],
)
def test_get_steps_rejects_bad_key_input_with_an_error(topic, problem_id):
    result = practice.get_steps(topic, problem_id)

    assert result["status"] == "error"


def test_well_formed_but_unknown_80_character_id_is_an_error():
    result = practice.get_steps(LA_TOPIC, "A" * 80)

    assert result["status"] == "error"


# ---------- check_answer: bank path ----------


def test_check_answer_accepts_an_equivalent_fraction_written_another_way():
    result = practice.check_answer(LA_TOPIC, LA_ID, r"\frac{-1}{8}")

    assert result["status"] == "ok"
    assert result["verdict"] == "correct"


def test_check_answer_accepts_the_plain_text_form_of_the_same_value():
    result = practice.check_answer(LA_TOPIC, LA_ID, "-1/8")

    assert result["verdict"] == "correct"


def test_check_answer_marks_a_wrong_value_incorrect():
    result = practice.check_answer(LA_TOPIC, LA_ID, "0")

    assert result["status"] == "ok"
    assert result["verdict"] == "incorrect"


def test_incorrect_result_does_not_reveal_the_reference_answer():
    result = practice.check_answer(LA_TOPIC, LA_ID, "0")
    body = json.dumps(result)

    assert r"\frac{1}{8}" not in body
    assert "-1/8" not in body
    assert "0.125" not in body


def test_check_answer_reports_method_checker_and_evidence():
    result = practice.check_answer(LA_TOPIC, LA_ID, r"\frac{-1}{8}")

    assert result["method"] == "sympy_equivalence"
    assert result["checked_by"] == "SymPy"
    assert result["evidence"] == EVIDENCE_TEN_POINTS


def test_checked_at_is_a_timezone_aware_utc_datetime():
    result = practice.check_answer(LA_TOPIC, LA_ID, "0")

    parsed = datetime.fromisoformat(result["checked_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_bank_path_ignores_a_client_reference_and_uses_the_bank_answer():
    right = practice.check_answer(LA_TOPIC, LA_ID, "-1/8", reference_latex="1")
    wrong = practice.check_answer(LA_TOPIC, LA_ID, "1", reference_latex="1")

    assert right["verdict"] == "correct"
    assert wrong["verdict"] == "incorrect"


def test_bank_path_explanation_names_the_verified_answer_not_the_key_on_the_page():
    result = practice.check_answer(LA_TOPIC, LA_ID, "0")

    assert BANK_KEY_SUBJECT in result["explanation"]
    assert OWN_KEY_PHRASE not in result["explanation"]


def test_check_answer_accepts_an_equivalent_expression_from_the_bank():
    result = practice.check_answer(CR_TOPIC, CR_ID, r"\frac{x}{\sqrt{x^{2} + 3}}")

    assert result["verdict"] == "correct"


def test_check_answer_marks_a_different_expression_incorrect():
    result = practice.check_answer(CR_TOPIC, CR_ID, r"\frac{1}{\sqrt{x^{2} + 3}}")

    assert result["verdict"] == "incorrect"


def test_constant_offset_from_the_bank_answer_is_unable_to_verify():
    result = practice.check_answer(CR_TOPIC, CR_ID, r"\frac{x}{\sqrt{x^{2} + 3}} + 3")

    assert result["verdict"] == "unable_to_verify"
    assert "constant" in result["explanation"]


def test_bank_answer_the_reader_cannot_read_gives_unable_to_verify():
    result = practice.check_answer(DQ_TOPIC, DQ_ID, "2 h^{2}")

    assert result["status"] == "ok"
    assert result["verdict"] == "unable_to_verify"
    assert "reference answer" in result["explanation"]


# ---------- check_answer: unreadable or unsafe student text ----------


@pytest.mark.parametrize(
    "answer",
    [
        "the answer is one",
        "{1, 2}",
        "[0, 1]",
        "__import__('os').system('echo hi')",
        "1; import os",
        r"\input{evil}",
        "os.system('x')",
        "9^9^9",
    ],
)
def test_unreadable_or_injection_like_text_is_unable_to_verify(answer):
    result = practice.check_answer(LA_TOPIC, LA_ID, answer)

    assert result["status"] == "ok"
    assert result["verdict"] == "unable_to_verify"
    assert result["evidence"] == NO_EVIDENCE


@pytest.mark.parametrize("answer", ["1\x00", "1\n+2", "1\x07"])
def test_control_characters_inside_the_answer_are_unable_to_verify(answer):
    result = practice.check_answer(LA_TOPIC, LA_ID, answer)

    assert result["verdict"] == "unable_to_verify"
    assert "control character" in result["explanation"]


@pytest.mark.parametrize("answer", ["", "   "])
def test_empty_answer_is_unable_to_verify(answer):
    result = practice.check_answer(LA_TOPIC, LA_ID, answer)

    assert result["verdict"] == "unable_to_verify"
    assert "empty" in result["explanation"]


def test_answer_longer_than_300_characters_is_unable_to_verify():
    result = practice.check_answer(LA_TOPIC, LA_ID, "1+" * 151)

    assert result["verdict"] == "unable_to_verify"
    assert "300" in result["explanation"]


def test_non_text_answer_is_unable_to_verify_not_an_exception():
    result = practice.check_answer(LA_TOPIC, LA_ID, 12345)

    assert result["status"] == "ok"
    assert result["verdict"] == "unable_to_verify"


def test_unknown_bank_id_on_check_is_an_error_not_a_verdict():
    result = practice.check_answer(LA_TOPIC, "NOPE99", "0")

    assert result["status"] == "error"
    assert "verdict" not in result


def test_bad_key_on_check_is_an_error():
    result = practice.check_answer("bad topic", LA_ID, "0")

    assert result["status"] == "error"


# ---------- check_answer: reference_latex path ----------


def test_reference_path_marks_an_equal_expression_correct():
    result = practice.check_answer(None, None, "x^{2} + 1", reference_latex=REFERENCE)

    assert result["verdict"] == "correct"
    assert OWN_KEY_PHRASE in result["explanation"]


def test_reference_path_accepts_an_empty_problem_id_too():
    result = practice.check_answer("", "", "x^{2}+1", reference_latex=REFERENCE)

    assert result["verdict"] == "correct"


def test_reference_path_marks_a_different_expression_incorrect_without_leaking():
    result = practice.check_answer(None, None, "x^{3}", reference_latex=REFERENCE)
    body = json.dumps(result)

    assert result["verdict"] == "incorrect"
    assert OWN_KEY_PHRASE in result["explanation"]
    assert "x^{2} + 1" not in body and "x^{2}+1" not in body


def test_reference_path_missing_reference_is_an_error():
    result = practice.check_answer(None, None, "x^{2}+1")

    assert result["status"] == "error"
    assert "reference_latex is required" in result["error"]


def test_reference_path_with_control_characters_in_reference_is_an_error():
    result = practice.check_answer(None, None, "x", reference_latex="x\x00")

    assert result["status"] == "error"


def test_reference_path_unreadable_reference_is_unable_to_verify():
    result = practice.check_answer(None, None, "x", reference_latex="y^{2}")

    assert result["verdict"] == "unable_to_verify"
    assert OWN_KEY_PHRASE in result["explanation"]
