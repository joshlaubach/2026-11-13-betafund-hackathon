"""Tests for core/derivative_checker.py, core/corrupt.py, and the power_rule gate."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.corrupt import corrupt_key  # noqa: E402
from core.derivative_checker import (  # noqa: E402
    ACCEPTED,
    NO_COMPARABLE_POINTS,
    UNREADABLE_KEY,
    UNREADABLE_PROBLEM,
    WRONG_KEY,
    check_derivative,
    parse_derivative_statement,
)

BANK_PATH = REPO_ROOT / "docs" / "verified_problems.json"
CHECKER_PATH = REPO_ROOT / "core" / "derivative_checker.py"
CORRUPT_PATH = REPO_ROOT / "core" / "corrupt.py"
GATE_PATH = REPO_ROOT / "scripts" / "gate_power_rule.py"
DEMO_PATH = REPO_ROOT / "scripts" / "demo_wrong_key.py"
NEW_FILES = (CHECKER_PATH, CORRUPT_PATH, GATE_PATH, DEMO_PATH)
FORBIDDEN_PATTERN = re.compile(r"\b(eval|exec|sympify|parse_expr)\b|sympy\.parsing")
TOPIC = "power_rule"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_bank_problem(problem_id: str) -> dict:
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return next(p for p in bank if p["topic"] == TOPIC and p["id"] == problem_id)


def test_parse_general_shape_returns_function_and_no_point():
    statement = r"Find $f'(x)$ for $f(x) = x^{4} + 3 x^{2} + 7$."
    assert parse_derivative_statement(statement) == {
        "function_latex": r"x^{4} + 3 x^{2} + 7",
        "at": None,
    }


def test_parse_point_shape_returns_function_and_point():
    statement = r"Find $f'(1)$ for $f(x) = - 3 x^{2} + \frac{3}{x^{2}}$. Give an exact answer."
    assert parse_derivative_statement(statement) == {
        "function_latex": r"- 3 x^{2} + \frac{3}{x^{2}}",
        "at": "1",
    }


def test_parse_negative_point():
    statement = r"Find $f'(-1)$ for $f(x) = 3 x^{6} - 2 x^{3} + 7$. Give an exact answer."
    parsed = parse_derivative_statement(statement)
    assert parsed is not None and parsed["at"] == "-1"


@pytest.mark.parametrize(
    "statement",
    [
        r"Solve $x^{2} = 4$.",
        r"Find $f'(x)$ for $g(x) = x$.",
        r"Find $\int x\,dx$.",
        "",
    ],
)
def test_parse_returns_none_for_other_statements(statement):
    assert parse_derivative_statement(statement) is None


def test_correct_key_is_accepted():
    verdict = check_derivative(r"x^{4} + 3 x^{2} + 7", "4 x^{3} + 6 x")
    assert verdict["ok"] is True
    assert verdict["outcome"] == ACCEPTED


def test_wrong_key_is_rejected_with_numbers_in_reason():
    verdict = check_derivative(r"x^{4} + 3 x^{2} + 7", "4 x^{3} + 6 x + 1")
    assert verdict["ok"] is False
    assert verdict["outcome"] == WRONG_KEY
    assert "at x = 0.3137 the checker computes 2.00568 but the key gives 3.00568" in verdict["reason"]


def test_plus_c_is_stripped_before_reading():
    verdict = check_derivative("x^{2}", "2 x + C")
    assert verdict["outcome"] == ACCEPTED


def test_unreadable_key_is_reported():
    verdict = check_derivative("x^{2}", "2 x + [")
    assert verdict["ok"] is False
    assert verdict["outcome"] == UNREADABLE_KEY


@pytest.mark.parametrize("hostile", ["__import__('os')", "__import__('os').system('echo hi')"])
def test_hostile_key_is_unreadable_and_does_not_raise(hostile):
    verdict = check_derivative("x^{2}", hostile)
    assert verdict["ok"] is False
    assert verdict["outcome"] == UNREADABLE_KEY


def test_unreadable_problem_is_reported():
    verdict = check_derivative("x^{[2]}", "2 x")
    assert verdict["ok"] is False
    assert verdict["outcome"] == UNREADABLE_PROBLEM


def test_point_key_accepted_when_value_matches():
    verdict = check_derivative("x^{3}", "3", at="1")
    assert verdict["outcome"] == ACCEPTED


def test_point_key_rejected_with_point_and_numbers():
    verdict = check_derivative("x^{3}", "4", at="1")
    assert verdict["outcome"] == WRONG_KEY
    assert "at x = 1 the checker computes 3 but the key gives 4" in verdict["reason"]


def test_point_without_real_value_has_no_comparable_points():
    verdict = check_derivative(r"\sqrt{x}", "1", at="-1")
    assert verdict["ok"] is False
    assert verdict["outcome"] == NO_COMPARABLE_POINTS


@pytest.mark.parametrize(
    "aliasing_key",
    [r"2x+\sin(10\pi x)", r"2x+\sin(20\pi x)"],
)
def test_grid_aliasing_keys_are_rejected(aliasing_key):
    verdict = check_derivative("x^{2}", aliasing_key)
    assert verdict["ok"] is False
    assert verdict["outcome"] == WRONG_KEY


def test_correct_key_still_accepted_with_non_grid_samples():
    assert check_derivative("x^{2}", "2 x")["outcome"] == ACCEPTED


def test_too_few_comparable_samples_is_no_comparable_points():
    verdict = check_derivative(r"\sqrt{x-2}", r"\frac{1}{2 \sqrt{x-2}}")
    assert verdict["outcome"] == NO_COMPARABLE_POINTS


def test_point_key_with_free_symbol_is_unreadable_key():
    verdict = check_derivative("x^{2}", "2x + (x-2)^2", at="2")
    assert verdict["ok"] is False
    assert verdict["outcome"] == UNREADABLE_KEY
    assert verdict["reason"] == "the key must be a number for f'(a)"


@pytest.mark.parametrize("kind", [0, 1, 2])
def test_corrupted_keys_are_rejected_as_wrong(kind):
    wrong = corrupt_key("2 x", kind)
    assert wrong is not None
    assert check_derivative("x^{2}", wrong)["outcome"] == WRONG_KEY


def test_corrupt_returns_none_for_identically_zero_key():
    assert corrupt_key("0", 1) is None
    assert corrupt_key("0", 2) is None


def test_corrupt_rejects_unknown_kind():
    with pytest.raises(ValueError):
        corrupt_key("2 x", 7)


def test_gate_logic_on_real_power_rule_problems():
    gate = load_module("gate_power_rule", GATE_PATH)
    for problem_id in ("PR01", "PR02", "PR05"):
        record = gate.evaluate_problem(load_bank_problem(problem_id))
        assert record["status"] == "supported", problem_id
        assert record["positive_ok"] is True, problem_id
        assert record["negative_passed"] == 3, problem_id
        assert record["negative_failed"] == 0, problem_id


def test_gate_supports_cube_root_problems():
    gate = load_module("gate_power_rule", GATE_PATH)
    for problem_id in ("PR28", "PR32"):
        record = gate.evaluate_problem(load_bank_problem(problem_id))
        assert record["status"] == "supported", problem_id
        assert record["positive_ok"] is True, problem_id
        assert record["negative_passed"] == 3, problem_id


def test_gate_counts_unreadable_key_as_positive_failure_not_unsupported():
    gate = load_module("gate_power_rule", GATE_PATH)
    problem = {
        "topic": TOPIC,
        "id": "FAKE",
        "level": 1,
        "statement": r"Find $f'(x)$ for $f(x) = x^{2}$.",
        "answer": {"type": "expression", "latex": "2 x + [", "sympy": "2*x"},
    }
    record = gate.evaluate_problem(problem)
    assert record["status"] == "supported"
    assert record["positive_ok"] is False
    assert any(reason.startswith("positive: unreadable_key") for reason in record["reasons"])


@pytest.mark.parametrize("path", NEW_FILES, ids=lambda p: p.name)
def test_new_files_do_not_use_eval_or_sympy_string_parsing(path):
    assert FORBIDDEN_PATTERN.search(path.read_text(encoding="utf-8")) is None
