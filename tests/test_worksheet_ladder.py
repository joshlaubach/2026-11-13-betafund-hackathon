"""Offline tests for the SymPy tier, the model ladder, call budgets, and regrading.

Every rung is a FakeSolver that records its calls. No network, no API key. The SymPy tests run
SymPy in a spawned child process, as production does.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import sympy_task  # noqa: E402
from core.bank_fallback import BANK_PATH  # noqa: E402
from core.ladder import Rungs  # noqa: E402
from core.skills import build_profile  # noqa: E402
from core.solvers import (  # noqa: E402
    ITEM_CAP_REASON,
    WORKSHEET_CALL_BUDGET,
    CallBudget,
    CallLedger,
    FakeSolver,
)
from core.worksheet import grade_item, regrade_item  # noqa: E402
from core.worksheet_types import (  # noqa: E402
    GRADE_LABELS,
    Grade,
    GradedItem,
    WorksheetItem,
)
from scripts.audit_bank import load_bank  # noqa: E402

LA01 = next(problem for problem in load_bank(BANK_PATH) if problem["id"] == "LA01")
LA01_STATEMENT = LA01["statement"]
LA01_ANSWER = LA01["answer"]["latex"]
DERIVATIVE = "Find $f'(x)$ for $f(x) = 5x^{7} - 3x^{2} + 11$."
DERIVATIVE_ANSWER = "35x^{6} - 6x"
LIMIT = "\\lim_{x \\to 3} \\frac{x^2-9}{x-3}"
GENERAL = "Differentiate the test function q(x) = x squared plus 2x."
GENERAL_ANSWER = "x^{2}+2x"
SECRET = "7x^{9}+11"


def item(statement: str, student: str | None, number: int = 1, topic: str | None = None) -> WorksheetItem:
    return WorksheetItem(
        number=number,
        statement_latex=statement,
        student_answer_latex=student,
        topic_guess=topic,
    )


def three(
    fast: FakeSolver | None = None, mid: FakeSolver | None = None, top: FakeSolver | None = None
) -> Rungs:
    return Rungs(fast or FakeSolver(), mid or FakeSolver(), top or FakeSolver())


def _calls_of(solver: FakeSolver) -> int:
    return len(solver.solve_calls) + len(solver.judge_calls)


# ---------------------------------------------------------------------------
# Tier b: sympy_computed
# ---------------------------------------------------------------------------


def test_sympy_derivative_is_marked_with_one_blind_haiku_cross_check():
    fast, mid, top = FakeSolver({DERIVATIVE: DERIVATIVE_ANSWER}), FakeSolver(), FakeSolver()
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), Rungs(fast, mid, top))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert grade.label == GRADE_LABELS["sympy_computed"]
    assert grade.bank_id is None
    assert "independent AI solve agreed" in grade.explanation
    assert fast.solve_calls == ((DERIVATIVE, None),)
    assert _calls_of(mid) == 0 and _calls_of(top) == 0


def test_haiku_disagreeing_with_sympy_is_unsure_and_shows_both_answers():
    fast = FakeSolver({DERIVATIVE: "35x^{6} - 7x"})
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three(fast))
    assert grade.verdict == "unsure"
    assert grade.method == "sympy_computed"
    assert "35x^{6} - 7x" in grade.explanation
    assert "read wrongly" in grade.explanation
    assert grade.reference_answer_latex is not None


def test_haiku_disagreement_never_flips_a_wrong_student_answer_to_correct():
    fast = FakeSolver({DERIVATIVE: "35x^{6} - 7x"})
    grade = grade_item(item(DERIVATIVE, "x"), three(fast))
    assert grade.verdict != "correct"
    assert grade.verdict == "unsure"


def test_haiku_agreeing_with_sympy_never_flips_a_correct_verdict_to_incorrect():
    fast = FakeSolver({DERIVATIVE: DERIVATIVE_ANSWER})
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three(fast))
    assert grade.verdict == "correct"


def test_haiku_error_keeps_the_sympy_mark_and_says_no_cross_check_was_available():
    fast = FakeSolver(error="scripted haiku failure")
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three(fast))
    assert grade.verdict == "correct"
    assert grade.method == "sympy_computed"
    assert "No independent AI cross-check was available" in grade.explanation


def test_limit_is_computed_as_six():
    grade = grade_item(item(LIMIT, "6"), three(FakeSolver({LIMIT: "6"})))
    assert grade.method == "sympy_computed"
    assert grade.verdict == "correct"
    assert grade.reference_answer_latex == "6"


def test_wrong_limit_answer_is_incorrect_against_sympy():
    grade = grade_item(item(LIMIT, "0"), three(FakeSolver({LIMIT: "6"})))
    assert grade.method == "sympy_computed"
    assert grade.verdict == "incorrect"


def test_unsupported_statements_fall_through_to_the_ai_ladder():
    statements = (
        GENERAL,
        "Evaluate $\\lim_{x \\to \\infty} \\frac{1}{x}$.",
        "Find the area of a circle of radius $r$.",
    )
    for statement in statements:
        assert sympy_task.parse_task(statement) is None
        grade = grade_item(item(statement, "x"), three())
        assert grade.method == "ai_judgment"


def test_timeout_falls_through_to_the_ai_ladder(monkeypatch):
    monkeypatch.setattr(sympy_task, "SYMPY_TIMEOUT_S", 0.001)
    task = sympy_task.parse_task(DERIVATIVE)
    assert task is not None
    assert sympy_task.compute_answer(task) is None
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three())
    assert grade.method == "ai_judgment"


def test_sympy_timeout_is_five_seconds():
    assert sympy_task.SYMPY_TIMEOUT_S == 5.0


# ---------------------------------------------------------------------------
# Tier c: ai_ladder and tier d: ai_judgment
# ---------------------------------------------------------------------------


def test_haiku_and_sonnet_agreeing_makes_no_opus_call():
    fast = FakeSolver({GENERAL: GENERAL_ANSWER})
    mid = FakeSolver({GENERAL: GENERAL_ANSWER})
    top = FakeSolver({GENERAL: "x^{2}+9x"})
    grade = grade_item(item(GENERAL, "2x+x^{2}"), Rungs(fast, mid, top))
    assert grade.verdict == "correct"
    assert grade.method == "ai_ladder"
    assert "2 of 2 independent AI solves agree" in grade.explanation
    assert len(fast.solve_calls) == 1
    assert len(mid.solve_calls) == 1
    assert top.solve_calls == ()


def test_disagreement_calls_opus_exactly_once_and_pairs_with_the_agreeing_solve():
    fast = FakeSolver({GENERAL: GENERAL_ANSWER})
    mid = FakeSolver({GENERAL: "x^{2}+3x"})
    top = FakeSolver({GENERAL: GENERAL_ANSWER})
    grade = grade_item(item(GENERAL, "2x+x^{2}"), Rungs(fast, mid, top))
    assert grade.verdict == "correct"
    assert grade.method == "ai_ladder"
    assert "2 of 3 independent AI solves agree" in grade.explanation
    assert len(top.solve_calls) == 1


def test_three_different_answers_give_unsure_listing_all_three():
    fast = FakeSolver({GENERAL: GENERAL_ANSWER})
    mid = FakeSolver({GENERAL: "x^{2}+3x"})
    top = FakeSolver({GENERAL: "x^{2}+5x"})
    grade = grade_item(item(GENERAL, "2x+x^{2}"), Rungs(fast, mid, top))
    assert grade.verdict == "unsure"
    assert grade.method == "ai_ladder"
    for answer in (GENERAL_ANSWER, "x^{2}+3x", "x^{2}+5x"):
        assert answer in grade.explanation
    assert len(top.solve_calls) == 1


def test_unreadable_solve_falls_to_the_judge_tier_on_sonnet():
    fast = FakeSolver({GENERAL: "\\int x\\,dx"})
    mid = FakeSolver({GENERAL: GENERAL_ANSWER}, verdict="incorrect")
    top = FakeSolver()
    grade = grade_item(item(GENERAL, "2x+x^{2}"), Rungs(fast, mid, top))
    assert grade.method == "ai_judgment"
    assert grade.verdict == "incorrect"
    assert len(mid.judge_calls) == 1
    assert top.solve_calls == ()


def test_per_item_call_cap_is_three():
    ledger = CallLedger(CallBudget(WORKSHEET_CALL_BUDGET))
    assert [ledger.take() for _ in range(3)] == [None, None, None]
    assert ledger.take() == ITEM_CAP_REASON


def test_worksheet_budget_exhaustion_gives_unsure_with_call_budget_reached():
    budget = CallBudget(2)
    fast = FakeSolver({GENERAL: GENERAL_ANSWER})
    mid = FakeSolver({GENERAL: GENERAL_ANSWER})
    rungs = Rungs(fast, mid, FakeSolver())
    first = grade_item(item(GENERAL, "2x+x^{2}", number=1), rungs, budget=budget)
    assert first.verdict == "correct"
    second = grade_item(item(GENERAL, "2x+x^{2}", number=2), rungs, budget=budget)
    assert second.verdict == "unsure"
    assert second.explanation == "call budget reached"
    assert len(fast.solve_calls) == 1
    assert len(mid.solve_calls) == 1


def test_worksheet_call_budget_is_forty():
    assert WORKSHEET_CALL_BUDGET == 40
    assert CallBudget().remaining == 40


def test_student_answer_is_never_sent_to_any_solve_call():
    fast = FakeSolver({DERIVATIVE: DERIVATIVE_ANSWER, GENERAL: GENERAL_ANSWER})
    mid = FakeSolver({GENERAL: GENERAL_ANSWER})
    top = FakeSolver({GENERAL: GENERAL_ANSWER})
    rungs = Rungs(fast, mid, top)
    grade_item(item(DERIVATIVE, SECRET), rungs)
    grade_item(item(GENERAL, SECRET), rungs)
    for solver in rungs:
        for call in solver.solve_calls:
            assert SECRET not in str(call)


# ---------------------------------------------------------------------------
# Regrading
# ---------------------------------------------------------------------------


def test_regrade_never_alters_bank_key_or_sympy_computed():
    bank_graded = GradedItem(
        item=item(LA01_STATEMENT, LA01_ANSWER, topic="algebraic"),
        grade=grade_item(item(LA01_STATEMENT, LA01_ANSWER, topic="algebraic"), three()),
    )
    sympy_graded = GradedItem(
        item=item(DERIVATIVE, DERIVATIVE_ANSWER),
        grade=grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three()),
    )
    wrong = FakeSolver({DERIVATIVE: "x", LA01_STATEMENT: "x"}, verdict="incorrect")
    rungs = Rungs(wrong, FakeSolver(verdict="incorrect"), FakeSolver())
    for graded in (bank_graded, sympy_graded):
        regraded = regrade_item(graded, rungs)
        assert regraded.grade.verdict == graded.grade.verdict
        assert regraded.grade.method == graded.grade.method
        assert regraded.changed_on_regrade is False
        assert regraded.regraded is True
    assert _calls_of(wrong) == 0


def test_regrade_of_an_ai_grade_uses_one_mid_solve_at_high_effort():
    mid = FakeSolver({GENERAL: "x^{2}"})
    first_rungs = Rungs(
        FakeSolver({GENERAL: GENERAL_ANSWER}), FakeSolver({GENERAL: GENERAL_ANSWER}), FakeSolver()
    )
    graded = GradedItem(
        item=item(GENERAL, GENERAL_ANSWER),
        grade=grade_item(item(GENERAL, GENERAL_ANSWER), first_rungs),
    )
    assert graded.grade.method == "ai_ladder"
    regraded = regrade_item(graded, Rungs(FakeSolver(), mid, FakeSolver()))
    assert mid.solve_calls == ((GENERAL, "high"),)
    assert regraded.changed_on_regrade is True
    assert regraded.grade.verdict == "incorrect"


# ---------------------------------------------------------------------------
# Labels and skills
# ---------------------------------------------------------------------------


def test_grade_labels_match_the_shared_wording():
    assert GRADE_LABELS["sympy_computed"] == (
        "Marked by Echo's checker: SymPy computed the answer itself"
    )
    assert GRADE_LABELS["ai_ladder"] == (
        "AI-graded: independent AI solves agree. SymPy only compared answers; the AI's answer "
        "is unchecked. Not verified by Echo"
    )
    assert GRADE_LABELS["ai_solve_sympy"] == (
        "AI-graded: an AI solved it and SymPy compared the two answers. SymPy did not check the "
        "AI's answer. Not verified by Echo"
    )


def test_each_grade_carries_the_label_for_its_method():
    grade = grade_item(item(DERIVATIVE, DERIVATIVE_ANSWER), three(FakeSolver({DERIVATIVE: DERIVATIVE_ANSWER})))
    assert grade.label == GRADE_LABELS[grade.method]


def test_sympy_computed_marks_count_as_verified_in_the_skill_profile():
    grade = Grade(
        verdict="correct",
        method="sympy_computed",
        label=GRADE_LABELS["sympy_computed"],
        explanation="checked",
        reference_answer_latex="35 x^{6} - 6 x",
    )
    graded = [GradedItem(item=item(DERIVATIVE, DERIVATIVE_ANSWER, topic="power_rule"), grade=grade)]
    profile = build_profile(graded)
    assert profile.skills[0].verified_marks == 1
