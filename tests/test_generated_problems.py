"""Tests for core.generated_problems and scripts/generate_echo_problems.py. No network calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import sympy

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from core.derivative_checker import check_derivative  # noqa: E402
from core.drafter import LABEL_ACCEPTED, build_statement  # noqa: E402
from core.generated_problems import (  # noqa: E402
    GENERATED_PATH,
    NET_CHANGE_TOPIC,
    load_generated,
    verify_integral,
    verify_pair,
)
from core.solvers import EQUAL, compare_answers  # noqa: E402
from generate_echo_problems import (  # noqa: E402
    AnswerDraft,
    AntiderivativeDraft,
    FunctionDraft,
    VelocityDraft,
    generate_one,
    generate_one_integral,
)


class ScriptedModel:
    """Fake call: each attempt returns the next (function, answer) pair from the script."""

    def __init__(self, pairs):
        self.pairs = list(pairs)
        self.index = -1
        self.answer_calls = 0

    def __call__(self, prompt, schema):
        if schema is AnswerDraft:
            self.index += 1
            self.answer_calls += 1
            return AnswerDraft(answer=self.pairs[self.index % len(self.pairs)][1])
        assert schema is FunctionDraft
        return FunctionDraft(function=self.pairs[self.index % len(self.pairs)][0])


def test_verify_pair_accepts_correct_pair_and_rejects_wrong_answer():
    assert verify_pair("(x^2+1)^3", "6*x*(x**2+1)**2")["ok"] is True
    wrong = verify_pair("(x^2+1)^3", "6*x*(x**2+1)")
    assert wrong["ok"] is False
    assert "derivative" in wrong["reason"]


@pytest.mark.parametrize(
    "function_text, answer_text",
    [
        ("__import__('os')", "1"),
        ("x; import os", "1"),
        ("lambda: x", "1"),
        ("y**2", "2*y"),
    ],
)
def test_verify_pair_rejects_unsafe_or_wrong_variable_text(function_text, answer_text):
    assert verify_pair(function_text, answer_text)["ok"] is False


def test_verify_pair_accepts_sqrt_quotient_with_simplified_answer():
    result = verify_pair("sqrt(x^2+3)/(x-1)", "(-x-3)/(sqrt(x^2+3)*(x-1)^2)")
    assert result["ok"] is True
    assert result["statement"] == build_statement(result["function_latex"], None)


def test_generate_one_returns_verified_problem():
    model = ScriptedModel([("(x^2+1)^3", "6*x*(x**2+1)**2")])
    problem = generate_one("chain_rule", 1, model, attempts=3, taken=set())
    assert problem is not None
    assert problem["label"] == LABEL_ACCEPTED
    assert problem["sympy_check"] == "passed"


def test_generate_one_gives_up_after_attempts_on_wrong_function():
    model = ScriptedModel([("x^2", "3*x^2")])
    assert generate_one("chain_rule", 1, model, attempts=4, taken=set()) is None
    assert model.answer_calls == 4


def test_generate_one_counts_exceptions_as_failed_attempts():
    def always_raises(prompt, schema):
        raise RuntimeError("network down")

    assert generate_one("quotient_rule", 2, always_raises, attempts=3, taken=set()) is None


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _problem(pid, topic, level, status="passed"):
    return {
        "id": pid,
        "topic": topic,
        "level": level,
        "statement": f"Find $f'(x)$ for $f(x) = {pid}$.",
        "answer_latex": "1",
        "function_latex": pid,
        "sympy_check": status,
    }


def test_load_generated_returns_empty_for_missing_malformed_or_wrong_shape(tmp_path):
    assert load_generated("chain_rule", 1, tmp_path / "missing.json") == []
    assert load_generated("chain_rule", 1, _write(tmp_path / "bad.json", "{not json")) == []
    assert load_generated("chain_rule", 1, _write(tmp_path / "shape.json", '{"version": 1, "problems": 5}')) == []
    assert load_generated("chain_rule", 1, _write(tmp_path / "list.json", "[1, 2]")) == []


def test_load_generated_filters_by_topic_and_level(tmp_path):
    data = {
        "version": 1,
        "problems": [_problem("a", "chain_rule", 1), _problem("b", "quotient_rule", 1)],
    }
    path = _write(tmp_path / "problems.json", json.dumps(data))
    result = load_generated("chain_rule", 1, path)
    assert len(result) == 1
    assert result[0]["id"] == "a"
    assert result[0]["label"] == LABEL_ACCEPTED
    assert set(result[0]) == {"id", "statement", "answer_latex", "level", "label"}
    assert load_generated("chain_rule", 2, path) == []


def test_load_generated_skips_problems_not_passed(tmp_path):
    data = {"version": 1, "problems": [_problem("a", "chain_rule", 1, status="failed")]}
    path = _write(tmp_path / "problems.json", json.dumps(data))
    assert load_generated("chain_rule", 1, path) == []


def test_saved_problems_file_is_verified():
    if not GENERATED_PATH.exists():
        pytest.skip(f"{GENERATED_PATH} does not exist yet; run scripts/generate_echo_problems.py first")
    data = json.loads(GENERATED_PATH.read_text(encoding="utf-8"))
    for entry in data["problems"]:
        if entry["topic"] == NET_CHANGE_TOPIC:
            continue  # checked by test_saved_net_change_problems_reverify
        # The file stores LaTeX, so re-check it with the same checker a student's answer uses.
        result = check_derivative(entry["function_latex"], entry["answer_latex"])
        assert result["ok"] is True, (entry["id"], result["reason"])
        assert entry["statement"] == build_statement(entry["function_latex"], None), entry["id"]


class ScriptedIntegral:
    """Fake call for the integral family: each attempt returns the next (F, v, a, b) from the script."""

    def __init__(self, drafts):
        self.drafts = list(drafts)
        self.index = -1

    def __call__(self, prompt, schema):
        if schema is AntiderivativeDraft:
            self.index += 1
            return AntiderivativeDraft(antiderivative=self.drafts[self.index % len(self.drafts)][0])
        assert schema is VelocityDraft
        _, velocity, a, b = self.drafts[self.index % len(self.drafts)]
        return VelocityDraft(velocity=velocity, a=a, b=b)


T = sympy.Symbol("t", real=True)


def test_verify_integral_accepts_exp_example():
    result = verify_integral("t - exp(-t)", "1 + exp(-t)", 0, 5)
    assert result["ok"] is True, result["reason"]
    v = 1 + sympy.exp(-T)
    assert all(float(v.subs(T, point)) > 0 for point in range(6))
    key = sympy.simplify(sympy.integrate(v, (T, 0, 5)))
    assert sympy.simplify(key - (6 - sympy.exp(-5))) == 0
    assert compare_answers(result["answer_latex"], "6 - e^{-5}").status == EQUAL
    assert result["statement"] == (
        "Compute $\\int_{0}^{5} v(t)\\,dt$ for $v(t) = " + result["velocity_latex"] + "$. Give an exact answer."
    )


@pytest.mark.parametrize(
    "antiderivative, velocity, a, b, reason",
    [
        ("t - exp(-t)", "2*t", 0, 5, "not the derivative"),
        ("t - exp(-t)", "1 + exp(-t)", 0, 6, "0 <= a < b <= 5"),
        ("t - exp(-t)", "1 + exp(-t)", 3, 3, "0 <= a < b <= 5"),
        ("__import__('os')", "1", 0, 5, "only t"),
        ("t - exp(-t)", "1 + exp(-t); import os", 0, 5, "only t"),
        ("s - exp(-s)", "1 + exp(-s)", 0, 5, "only t"),
    ],
)
def test_verify_integral_rejects_bad_input(antiderivative, velocity, a, b, reason):
    result = verify_integral(antiderivative, velocity, a, b)
    assert result["ok"] is False
    assert reason in result["reason"]


def test_verify_integral_rejects_negative_velocity():
    # v = 1 - 2t is exact and goes negative after t = 0.5. (A constant velocity such as -1 is rejected earlier
    # by the must-use-only-t rule, so it cannot test the sign check.)
    result = verify_integral("t - t^2", "1 - 2*t", 0, 5)
    assert result["ok"] is False
    assert "negative" in result["reason"]


def test_generate_one_integral_returns_verified_problem():
    model = ScriptedIntegral([("t - exp(-t)", "1 + exp(-t)", 0, 5)])
    problem = generate_one_integral(1, model, attempts=3, taken=set())
    assert problem is not None
    assert problem["label"] == LABEL_ACCEPTED
    assert problem["topic"] == NET_CHANGE_TOPIC
    assert problem["sympy_check"] == "passed"
    assert problem["antiderivative"] == "t - exp(-t)"
    assert problem["velocity_text"] == "1 + exp(-t)"
    assert (problem["a"], problem["b"]) == (0, 5)


def test_generate_one_integral_returns_none_when_every_call_fails():
    def always_raises(prompt, schema):
        raise RuntimeError("network down")

    assert generate_one_integral(4, always_raises, attempts=3, taken=set()) is None


def test_saved_net_change_problems_reverify():
    if not GENERATED_PATH.exists():
        pytest.skip(f"{GENERATED_PATH} does not exist yet; run scripts/generate_echo_problems.py first")
    data = json.loads(GENERATED_PATH.read_text(encoding="utf-8"))
    entries = [entry for entry in data["problems"] if entry["topic"] == NET_CHANGE_TOPIC]
    if not entries:
        pytest.skip(f"no {NET_CHANGE_TOPIC} entries saved yet")
    for entry in entries:
        assert "antiderivative" in entry and "velocity_text" in entry, entry["id"]
        result = verify_integral(entry["antiderivative"], entry["velocity_text"], entry["a"], entry["b"])
        assert result["ok"] is True, (entry["id"], result["reason"])
        assert result["answer_latex"] == entry["answer_latex"], entry["id"]
        assert result["statement"] == entry["statement"], entry["id"]


def test_a_bare_function_name_is_a_failed_check_not_a_crash():
    # Codex review: parse_expr("sqrt") returns a Python function; this must fail cleanly.
    assert verify_pair("sqrt", "x")["ok"] is False
    assert verify_integral("sqrt", "x", 0, 1)["ok"] is False


def test_a_key_the_practice_checker_would_reject_is_not_stored():
    # Codex review: a 14-term root sum verifies but its LaTeX is over the practice limit of 300 characters.
    terms = "+".join(f"sqrt({p})/{p + 1}" for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43])
    result = verify_integral(f"t**2/2+t*({terms})", f"t+{terms}", 0, 1)
    assert result["ok"] is False
