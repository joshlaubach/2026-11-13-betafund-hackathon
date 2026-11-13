"""Practice problems from the verified bank: worked steps, and a deterministic answer check.

get_steps serves the verified steps and answer of an eligible bank problem. check_answer compares a
typed answer with a reference using SymPy: the bank's own answer when problem_id names an eligible
bank problem, otherwise a reference the caller supplies. No model is called here.

The comparison is core.solvers.compare_answers, the helper the bank_key grader uses. It runs inside
the spawned child process from core.sympy_task, so a hung computation is killed at its timeout.
Student text is read only by core.latex_reader (through is_readable and compare_answers), never by
a direct SymPy parser. Any failure gives unable_to_verify, never a guessed verdict.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import NamedTuple, Optional

from core.bank_fallback import BANK_PATH
from core.solvers import (
    DIFFERENT,
    DOMAIN_DIFFERS,
    EQUAL,
    UNKNOWN,
    Comparison,
    compare_answers,
    is_readable,
)
from core.sympy_task import _run_in_child
from scripts.audit_bank import classify, load_bank

logger = logging.getLogger(__name__)

MAX_ID_LENGTH = 80
MAX_ANSWER_LENGTH = 300
ID_PATTERN = re.compile(r"[A-Za-z0-9_\-]{1,80}")
STATUS_OK = "ok"
STATUS_ERROR = "error"
SOURCE_BANK = "bank"
CHECKER = "SymPy"
METHOD = "sympy_equivalence"
VERDICT_CORRECT = "correct"
VERDICT_INCORRECT = "incorrect"
VERDICT_UNABLE = "unable_to_verify"
SUBJECT_BANK = "the verified answer for this problem"
SUBJECT_REFERENCE = "the reference answer from the problem's own key as shown on the page"
NO_COMPARISON = "no comparison was made"
REASON_REFERENCE_UNREADABLE = "the checker cannot read the reference answer"
REASON_STUDENT_UNREADABLE = "the checker cannot read the answer as math"
REASON_CONSTANT_OFFSET = (
    "it differs from the reference by a constant, so the checker cannot tell whether that is intended"
)
REASON_TOO_FEW_POINTS = "the checker could not evaluate enough sample points to compare"
REASON_NOT_FINISHED = "the check did not finish"
ERROR_KEY = (
    f"topic and problem_id must be 1 to {MAX_ID_LENGTH} letters, digits, underscores or hyphens"
)
ERROR_NOT_ELIGIBLE = "no eligible bank problem has that topic and id"
ERROR_BANK_UNAVAILABLE = "the verified problem bank could not be read"
ERROR_REFERENCE_MISSING = "reference_latex is required when problem_id is empty"


class _Target(NamedTuple):
    """The reference to compare against, and how the explanation names it."""

    reference: str
    subject: str


class _Reading(NamedTuple):
    """What the child process found: whether each side could be read, and the comparison."""

    reference_readable: bool
    student_readable: bool
    comparison: Comparison


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _error(message: str) -> dict:
    return {"status": STATUS_ERROR, "error": message}


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _key_error(topic: object, problem_id: object) -> Optional[str]:
    for value in (topic, problem_id):
        if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
            return ERROR_KEY
    return None


def _text_error(value: object) -> Optional[str]:
    """Why a typed answer is not usable, or None. The text is stripped before the length check."""
    if not isinstance(value, str):
        return "must be text"
    stripped = value.strip()
    if not stripped:
        return "is empty"
    if len(stripped) > MAX_ANSWER_LENGTH:
        return f"is longer than {MAX_ANSWER_LENGTH} characters"
    if any(unicodedata.category(char).startswith("C") for char in stripped):
        return "contains a control character"
    return None


def _clean(value: str) -> str:
    return value.strip()


def _answer_latex(problem: dict) -> str:
    return str((problem.get("answer") or {}).get("latex", ""))


def _eligible_index() -> dict[tuple[str, str], dict]:
    """Eligible bank problems keyed by (topic, id). Reads the bank fresh on every call."""
    index: dict[tuple[str, str], dict] = {}
    for problem in load_bank(BANK_PATH):
        if classify(problem) is None:
            index.setdefault((str(problem["topic"]), str(problem["id"])), problem)
    return index


def get_steps(topic: object, problem_id: object) -> dict:
    """The verified steps and answer for an eligible bank problem, or an error status."""
    key_error = _key_error(topic, problem_id)
    if key_error is not None:
        return _error(key_error)
    try:
        index = _eligible_index()
    except (OSError, ValueError) as error:
        logger.error("practice steps: bank unreadable: %s: %s", type(error).__name__, error)
        return _error(ERROR_BANK_UNAVAILABLE)
    problem = index.get((topic, problem_id))
    if problem is None:
        return _error(ERROR_NOT_ELIGIBLE)
    return {
        "status": STATUS_OK,
        "topic": topic,
        "problem_id": problem_id,
        "steps": [str(step) for step in problem.get("steps") or []],
        "answer_latex": _answer_latex(problem),
        "source": SOURCE_BANK,
    }


def _resolve_target(
    topic: object, problem_id: object, reference_latex: object
) -> tuple[Optional[_Target], Optional[str]]:
    """The reference to check against, or an error message. A bank id always wins over a client reference."""
    if _is_blank(problem_id):
        if reference_latex is None:
            return None, ERROR_REFERENCE_MISSING
        reference_error = _text_error(reference_latex)
        if reference_error is not None:
            return None, f"reference_latex {reference_error}"
        return _Target(_clean(reference_latex), SUBJECT_REFERENCE), None
    key_error = _key_error(topic, problem_id)
    if key_error is not None:
        return None, key_error
    try:
        problem = _eligible_index().get((topic, problem_id))
    except (OSError, ValueError) as error:
        logger.error("practice check: bank unreadable: %s: %s", type(error).__name__, error)
        return None, ERROR_BANK_UNAVAILABLE
    if problem is None:
        return None, ERROR_NOT_ELIGIBLE
    return _Target(_answer_latex(problem), SUBJECT_BANK), None


def _compare_in_child(pair: tuple[str, str]) -> _Reading:
    """Runs in the child process. Reads both sides with the safe reader, then compares them."""
    reference_latex, student_latex = pair
    reference_readable = is_readable(reference_latex)
    student_readable = is_readable(student_latex)
    if not (reference_readable and student_readable):
        return _Reading(reference_readable, student_readable, Comparison(UNKNOWN))
    return _Reading(True, True, compare_answers(reference_latex, student_latex))


def _verdict(verdict: str, explanation: str, evidence: str, checked_at: str) -> dict:
    return {
        "status": STATUS_OK,
        "verdict": verdict,
        "method": METHOD,
        "checked_by": CHECKER,
        "checked_at": checked_at,
        "explanation": explanation,
        "evidence": evidence,
    }


def _unable(subject: str, reason: str, checked_at: str) -> dict:
    return _verdict(
        VERDICT_UNABLE,
        f"Your answer could not be checked against {subject}: {reason}.",
        NO_COMPARISON,
        checked_at,
    )


def _compared(points: int) -> str:
    return f"compared at {points} sample points by numeric evaluation"


def _from_comparison(comparison: Comparison, subject: str, checked_at: str) -> dict:
    if comparison.status == EQUAL:
        return _verdict(
            VERDICT_CORRECT,
            f"Your answer matches {subject}.",
            _compared(comparison.points),
            checked_at,
        )
    if comparison.status in (DIFFERENT, DOMAIN_DIFFERS):
        return _verdict(
            VERDICT_INCORRECT,
            f"Your answer does not match {subject}.",
            _compared(comparison.points),
            checked_at,
        )
    if comparison.constant_offset:
        return _unable(subject, REASON_CONSTANT_OFFSET, checked_at)
    return _unable(subject, REASON_TOO_FEW_POINTS, checked_at)


def _from_reading(reading: object, subject: str, checked_at: str) -> dict:
    if not isinstance(reading, _Reading):
        return _unable(subject, REASON_NOT_FINISHED, checked_at)
    if not reading.reference_readable:
        return _unable(subject, REASON_REFERENCE_UNREADABLE, checked_at)
    if not reading.student_readable:
        return _unable(subject, REASON_STUDENT_UNREADABLE, checked_at)
    return _from_comparison(reading.comparison, subject, checked_at)


def check_answer(
    topic: object,
    problem_id: object,
    answer_latex: object,
    reference_latex: object = None,
) -> dict:
    """Compare a typed answer with the reference by SymPy. Never reveals the reference in the result."""
    checked_at = _now_utc()
    target, error = _resolve_target(topic, problem_id, reference_latex)
    if error is not None or target is None:
        return _error(error or ERROR_NOT_ELIGIBLE)
    answer_error = _text_error(answer_latex)
    if answer_error is not None:
        return _unable(target.subject, f"the answer {answer_error}", checked_at)
    try:
        reading = _run_in_child(_compare_in_child, (target.reference, _clean(answer_latex)))
    except Exception as error:  # any failure is an unchecked answer, never a guess
        logger.error("practice check failed: %s: %s", type(error).__name__, error)
        reading = None
    return _from_reading(reading, target.subject, checked_at)
