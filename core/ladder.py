"""The model ladder for worksheet grading: Haiku and Sonnet solve blind, Opus breaks a tie.

Rungs are three solvers, one per model. Their model names come from ECHO_MODEL_FAST,
ECHO_MODEL_MID, and ECHO_MODEL_TOP, with defaults. Every solve and judge call receives the full
statement (the shared setup plus the part's question). grade_unmatched is the entry point for an
item with no bank match: SymPy first (core.sympy_task), then the AI ladder, then the judge tier
(Sonnet, only when an answer cannot be compared). regrade_mark gives one fresh Sonnet solve.
"""

from __future__ import annotations

import logging
import os
from typing import NamedTuple, Optional

from core.definitions import missing_definitions
from core.drafter import DEFAULT_EFFORT
from core.solvers import (
    ITEM_CALL_CAP,
    JUDGE_FAILED_EXPLANATION,
    AnswerSolver,
    Attempt,
    CallBudget,
    CallLedger,
    FakeSolver,
    LiveSolver,
    Mark,
    Question,
    ask_solve,
    compare_answers,
    comparison_mark,
    is_readable,
    log_failure,
)
from core.sympy_task import sympy_mark
from core.worksheet_types import GradeMethod

logger = logging.getLogger(__name__)
ENV_MODEL_FAST = "ECHO_MODEL_FAST"
ENV_MODEL_MID = "ECHO_MODEL_MID"
ENV_MODEL_TOP = "ECHO_MODEL_TOP"
DEFAULT_MODEL_FAST = "claude-haiku-5-5"
DEFAULT_MODEL_MID = "claude-sonnet-5-5"
DEFAULT_MODEL_TOP = "claude-opus-5-5"
REGRADE_EFFORT = "high"
AI_LADDER: GradeMethod = "ai_ladder"
SINGLE_SOLVE: GradeMethod = "ai_solve_sympy"
JUDGE: GradeMethod = "ai_judgment"
AGREED_PHRASE = "the agreed AI answer"
REGRADED_PHRASE = "the regraded AI answer"
AGREE_NOTE = "{count} of {total} independent AI solves agree."
THREE_WAY = (
    "The three AI solves gave {first}, {second}, and {third}; no two agree, so this mark is unsure."
)
TIEBREAK_FAILED = (
    "Two AI solves disagreed and the tiebreak solve gave no usable answer, so this mark is unsure."
)
JUDGED = (
    "The student's answer {student} could not be checked by SymPy, so the AI judge marked it "
    "{verdict} from the statement alone."
)
UNSURE_SUFFIX = ", so this mark is unsure."
REASON_NO_CONTEXT = "no shared setup defines {names} for this part"
REASON_STUDENT_UNREADABLE = "the student's answer could not be read by SymPy"
REASON_SOLVE_UNREADABLE = "an AI solve could not be read by SymPy"
REASON_JUDGE_UNSURE = "the AI judge could not tell from the statement alone"
UNSURE = "unsure"


class Rungs(NamedTuple):
    """The fast (blind solve), mid (blind solve and the judge), and top (tiebreak) solvers."""

    fast: AnswerSolver
    mid: AnswerSolver
    top: AnswerSolver


def _env_model(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def rung_models() -> tuple[str, str, str]:
    """The fast, mid, and top model names from the environment, with defaults."""
    return (
        _env_model(ENV_MODEL_FAST, DEFAULT_MODEL_FAST),
        _env_model(ENV_MODEL_MID, DEFAULT_MODEL_MID),
        _env_model(ENV_MODEL_TOP, DEFAULT_MODEL_TOP),
    )


def live_rungs(effort: str = DEFAULT_EFFORT) -> Rungs:
    """Three live solvers, one per rung model. Only this builds network clients."""
    fast, mid, top = rung_models()
    return Rungs(LiveSolver(fast, effort), LiveSolver(mid, effort), LiveSolver(top, effort))


def fake_rungs() -> Rungs:
    """Three scripted solvers that never touch the network."""
    return Rungs(FakeSolver(), FakeSolver(), FakeSolver())


def as_rungs(solver: "AnswerSolver | Rungs") -> Rungs:
    """Rungs unchanged, or one solver used for every rung."""
    if isinstance(solver, Rungs):
        return solver
    return Rungs(solver, solver, solver)


def _readable_answer(answer: Optional[str]) -> bool:
    return answer is not None and is_readable(answer)


def _agrees(left: str, right: str) -> bool:
    return compare_answers(left, right).status == "equal"


def _unsure_reason(question: Question, cause: str) -> str:
    """Say what was missing: a definition from the setup, or else the given cause."""
    missing = missing_definitions(question.statement, question.context)
    if missing:
        return REASON_NO_CONTEXT.format(names=", ".join(missing))
    return cause


def _judge(
    question: Question, rung: AnswerSolver, ledger: CallLedger, effort: Optional[str], cause: str
) -> Mark:
    """The judge tier: Sonnet judges the written answer. Only used when no answer can be compared."""
    refusal = ledger.take()
    if refusal is not None:
        return Mark(UNSURE, JUDGE, refusal)
    try:
        verdict = rung.judge(question.full, question.judged, effort).verdict
    except Exception as error:  # a judge failure is an unsure mark, never a crash
        log_failure(logger, "judge call failed", error)
        return Mark(UNSURE, JUDGE, JUDGE_FAILED_EXPLANATION)
    if verdict == UNSURE:
        return Mark(UNSURE, JUDGE, _unsure_reason(question, cause) + UNSURE_SUFFIX)
    return Mark(verdict, JUDGE, JUDGED.format(student=question.compared, verdict=verdict))


def _against_agreed(
    question: Question,
    reference: str,
    agreeing: int,
    total: int,
    rungs: Rungs,
    ledger: CallLedger,
    effort: Optional[str],
) -> Mark:
    comparison = compare_answers(reference, question.compared)
    mark = comparison_mark(comparison, question.compared, reference, AI_LADDER, AGREED_PHRASE)
    if mark is None:
        return _judge(question, rungs.mid, ledger, effort, REASON_STUDENT_UNREADABLE)
    if mark.verdict == UNSURE:
        return mark  # an unsure reason (such as + C) is shown as it is
    note = AGREE_NOTE.format(count=agreeing, total=total)
    return mark._replace(explanation=f"{mark.explanation} {note}")


def _tiebreak(
    question: Question,
    fast_answer: str,
    mid_answer: str,
    rungs: Rungs,
    ledger: CallLedger,
    effort: Optional[str],
) -> Mark:
    """Opus solves once. It settles the disagreement only by matching one of the two answers."""
    top = ask_solve(rungs.top, question.full, ledger, effort)
    if top.refusal is not None:
        return Mark(UNSURE, AI_LADDER, top.refusal)
    if top.answer is None:
        return Mark(UNSURE, AI_LADDER, TIEBREAK_FAILED)
    if _agrees(fast_answer, top.answer):
        return _against_agreed(question, fast_answer, 2, 3, rungs, ledger, effort)
    if _agrees(mid_answer, top.answer):
        return _against_agreed(question, mid_answer, 2, 3, rungs, ledger, effort)
    listing = THREE_WAY.format(first=fast_answer, second=mid_answer, third=top.answer)
    return Mark(UNSURE, AI_LADDER, listing)


def ai_mark(
    question: Question,
    rungs: Rungs,
    ledger: CallLedger,
    effort: Optional[str] = None,
) -> Mark:
    """The AI ladder. Haiku and Sonnet solve blind; Opus only when they differ.

    The judge tier takes over when the student's answer or either solve cannot be read by SymPy.
    """
    if not is_readable(question.compared):
        return _judge(question, rungs.mid, ledger, effort, REASON_STUDENT_UNREADABLE)
    fast = ask_solve(rungs.fast, question.full, ledger, effort)
    if fast.refusal is not None:
        return Mark(UNSURE, AI_LADDER, fast.refusal)
    mid = ask_solve(rungs.mid, question.full, ledger, effort)
    if mid.refusal is not None:
        return Mark(UNSURE, AI_LADDER, mid.refusal)
    if not (_readable_answer(fast.answer) and _readable_answer(mid.answer)):
        return _judge(question, rungs.mid, ledger, effort, REASON_SOLVE_UNREADABLE)
    if _agrees(str(fast.answer), str(mid.answer)):
        return _against_agreed(question, str(fast.answer), 2, 2, rungs, ledger, effort)
    return _tiebreak(question, str(fast.answer), str(mid.answer), rungs, ledger, effort)


def grade_unmatched(
    question: Question,
    rungs: Rungs,
    ledger: CallLedger,
    effort: Optional[str] = None,
) -> Mark:
    """An item with no bank match: SymPy when the part is a derivative, limit, value, or integral, else the AI ladder."""
    checked = sympy_mark(
        question.statement, question.answers, rungs.fast, ledger, question.context
    )
    if checked is not None:
        return checked
    return ai_mark(question, rungs, ledger, effort)


def regrade_mark(question: Question, rungs: Rungs) -> Mark:
    """One fresh blind solve by the mid rung at REGRADE_EFFORT, compared with the student's answer."""
    ledger = CallLedger(CallBudget(ITEM_CALL_CAP))
    solved: Attempt = ask_solve(rungs.mid, question.full, ledger, REGRADE_EFFORT)
    if solved.refusal is None and _readable_answer(solved.answer):
        comparison = compare_answers(str(solved.answer), question.compared)
        mark = comparison_mark(
            comparison, question.compared, str(solved.answer), SINGLE_SOLVE, REGRADED_PHRASE
        )
        if mark is not None:
            return mark
    return _judge(question, rungs.mid, ledger, REGRADE_EFFORT, REASON_JUDGE_UNSURE)
