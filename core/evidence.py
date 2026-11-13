"""The boundary between grading and tutoring.

Grading (core/worksheet.py, core/ladder.py, core/practice.py) records what it found: a verdict, a method and a
reason. Tutoring needs a different question answered: how sure may the tutor sound? This module is the only place
that turns the first into the second.

verification_of() says whether a mark was actually verified. stance_of() says how the tutor may talk about the
student's answer. A mark that was not verified is never confirmed wrong: failing to verify an answer is not
evidence that it is incorrect. help_level() decides how much help the next reply gives. leaks_internals() catches
grading vocabulary (tools, records, method names) before it reaches a student.

Everything here is pure and offline. The student-facing words below never name a tool, a model or a record.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

Verification = Literal["verified", "unverified", "unavailable"]
Stance = Literal["confirmed_correct", "confirmed_incorrect", "likely_correct", "likely_incorrect", "unknown"]
HelpLevel = Literal["ask", "hint", "step", "solution"]

# Methods where Echo's own program compared the answer with a verified or computed reference.
VERIFIED_METHODS = ("bank_key", "sympy_computed")
# Independent AI solves that agree, compared by a program. Evidence, but not verification.
LIKELY_METHODS = ("ai_ladder", "ai_solve_sympy")
# Unsure reasons that mean the check itself could not run, rather than the answer being hard to judge.
UNAVAILABLE_REASONS = ("no_verdict", "reading")

# Earlier tutor replies, hints shown and wrong attempts together decide how much help comes next.
HINT_AFTER = 1
STEP_AFTER = 3
SOLUTION_AFTER = 5

STANCE_WORDS: dict[str, str] = {
    "confirmed_correct": "The answer is confirmed correct.",
    "confirmed_incorrect": "The answer is confirmed incorrect: it does not match a checked reference answer.",
    "likely_correct": "The answer looks correct, but nothing has confirmed it. Do not say it is right for certain.",
    "likely_incorrect": "The answer may be wrong, but nothing has confirmed it. Do not tell the student it is wrong.",
    "unknown": "It is not known whether the answer is right. Do not say it is right or wrong.",
}
# Why the answer is uncertain, in words that are safe to relay. Used only when the stance is not confirmed.
REASON_WORDS: dict[str, str] = {
    "reading": "the handwriting may not have been read correctly",
    "format": "the answer is written in a form that is hard to compare automatically",
    "disagreement": "independent attempts at the problem did not agree with each other",
    "no_verdict": "a technical problem stopped the check from finishing",
    "rule": "a detail such as the constant of integration or the domain needs a closer look",
}
HELP_INSTRUCTIONS: dict[str, str] = {
    "ask": "Ask exactly one focused question that points at the student's next step. Do not give the answer or a method name.",
    "hint": "Give one concrete hint that names the idea or the next move. Do not give the final answer.",
    "step": "Work out the next step with the student, and leave the last step for them to do.",
    "solution": "Give a complete worked solution, one step per line, because the student asked for it or has been stuck for a while.",
}

SOLUTION_REQUEST = re.compile(
    r"\b(?:(?:show|give|write|see|need|want)\b.{0,25}\b(?:solution|answer|working|(?:worked )?examples?)"
    r"|just tell me|tell me the answer|walk me through (?:it|the whole)|solve it for me)\b",
    re.IGNORECASE,
)
HINT_REQUEST = re.compile(r"\b(?:hint|stuck|clue|nudge|where do i start|help me start|get started)\b", re.IGNORECASE)
HOW_CHECKED_REQUEST = re.compile(
    r"\bhow\b.{0,30}\b(?:check|checked|verif\w*|mark\w*|grad\w*)\b"
    r"|\bwho\b.{0,20}\b(?:check|checked|verif\w*|mark\w*|grad\w*)\b"
    r"|\bwhy\b.{0,30}\b(?:marked|graded)\b"
    r"|\b(?:is|was) (?:this|it) (?:verified|checked)\b",
    re.IGNORECASE,
)
# Grading vocabulary that must not reach a student unprompted: method ids, tools, records and model talk.
INTERNAL_LANGUAGE = re.compile(
    r"\bsympy\b|\bverification (?:tool|status|step|pipeline)\b|\bgrading (?:record|pipeline|logic|method)\b"
    r"|\bthe record\b|\bai[- ]judge\w*\b|\bjudged (?:it |this |the answer )?(?:from|on its own|by an ai)\b"
    r"|\bmarked (?:it |this |the answer )?(?:as )?(?:incorrect|wrong)\b|\bnot (?:been )?verified\b|\bunverified\b"
    r"|\b(?:bank_key|sympy_computed|ai_ladder|ai_solve_sympy|ai_judgment|not_graded)\b"
    r"|\bstack ?trace\b|\bsystem prompt\b|\bconfidence score\b|\bdiagnostics?\b",
    re.IGNORECASE,
)


def verification_of(method: str, verdict: str, reason: Optional[str] = None) -> Verification:
    """Whether a mark was verified. "unavailable" means the check could not run, "unverified" means no program checked it."""
    if verdict == "unsure":
        return "unavailable" if reason in UNAVAILABLE_REASONS or method == "not_graded" else "unverified"
    return "verified" if method in VERIFIED_METHODS else "unverified"


def stance_of(method: str, verdict: str, reason: Optional[str] = None) -> Stance:
    """How sure the tutor may sound. Only a verified mark is ever confirmed.

    A single AI judge that read the statement alone (ai_judgment) is not enough to call an answer wrong or right,
    because that is the path taken when no program could compare the answer.
    """
    if verdict not in ("correct", "incorrect"):
        return "unknown"
    side = "correct" if verdict == "correct" else "incorrect"
    if method in VERIFIED_METHODS:
        return "confirmed_correct" if side == "correct" else "confirmed_incorrect"
    if method in LIKELY_METHODS:
        return "likely_correct" if side == "correct" else "likely_incorrect"
    return "unknown"


def attempt_stance(verdict: str) -> Stance:
    """The stance for a practice-check verdict. That check compares with a verified key, so a decisive verdict is confirmed."""
    if verdict == "correct":
        return "confirmed_correct"
    if verdict == "incorrect":
        return "confirmed_incorrect"
    return "unknown"  # "unsure" and "unable_to_verify" both mean it could not be told


def is_confirmed(stance: Stance) -> bool:
    return stance.startswith("confirmed_")


def asks_for_solution(message: str) -> bool:
    return SOLUTION_REQUEST.search(message) is not None


def asks_for_hint(message: str) -> bool:
    return HINT_REQUEST.search(message) is not None


def asks_how_checked(message: str) -> bool:
    """True when the student is asking how a mark was made. Only then may a reply describe the method."""
    return HOW_CHECKED_REQUEST.search(message) is not None


def help_level(message: str, rounds: int) -> HelpLevel:
    """How much help the next reply gives. rounds counts earlier tutor replies, hints shown and wrong attempts.

    Socratic first: the first reply asks a question. Each round makes the help more specific, and a request for
    the solution, or a long stretch of being stuck, gets the full worked solution.
    """
    if asks_for_solution(message) or rounds >= SOLUTION_AFTER:
        return "solution"
    if rounds >= STEP_AFTER:
        return "step"
    if rounds >= HINT_AFTER or asks_for_hint(message):
        return "hint"
    return "ask"


def leaks_internals(text: str, allow_method_talk: bool = False) -> bool:
    """True when a reply uses grading vocabulary. Allowed only when the student asked how a mark was made."""
    return not allow_method_talk and INTERNAL_LANGUAGE.search(text) is not None


def uncertainty_words(reason: Optional[str]) -> str:
    """A plain phrase for why an answer is uncertain, or an empty string."""
    return REASON_WORDS.get(reason or "", "")
