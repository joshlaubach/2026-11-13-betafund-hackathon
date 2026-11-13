"""Shared data shapes for the worksheet loop: read -> grade -> skill profile -> recommend.

Every track (reader/grader, skill profile, server, page) uses these exact shapes.
All models are frozen, so a result is never edited after it is built.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Confidence = Literal["low", "medium", "high"]
Verdict = Literal["correct", "incorrect", "unsure"]
GradeMethod = Literal["bank_key", "sympy_computed", "ai_ladder", "ai_solve_sympy", "ai_judgment"]
SkillStatus = Literal["solid", "shaky", "weak", "not_enough_data"]

# Plain-words labels shown to the user next to every mark. One place, so the page and the
# server never disagree about what a mark claims.
GRADE_LABELS: dict[str, str] = {
    "bank_key": "Marked against a verified bank answer, compared by SymPy",
    "sympy_computed": "Marked by Echo's checker: SymPy computed the answer itself",
    "ai_ladder": "AI-graded: independent AI solves agree. SymPy only compared answers; the AI's answer is unchecked. Not verified by Echo",
    "ai_solve_sympy": "AI-graded: an AI solved it and SymPy compared the two answers. SymPy did not check the AI's answer. Not verified by Echo",
    "ai_judgment": "AI-graded: AI judgment only. Not verified by Echo",
}
GRADE_DISCLAIMER = (
    "AI can make mistakes, so marks that are not verified may be wrong. "
    "Use Regrade or check any mark you are unsure about."
)


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class WorksheetItem(Frozen):
    """One part read from a worksheet photo, with the student's written answer.

    statement_latex is the part's own question only. context_latex is the shared setup that the
    code copies in after reading. final_answers_latex are the student's final answers in order, and
    explanation_text is the student's written sentence, which is shown but never graded.
    """

    number: int
    statement_latex: str
    student_answer_latex: Optional[str] = None  # the full written line, working included
    topic_guess: Optional[str] = None  # a bank topic id, or None
    confidence: Confidence = "medium"
    notes: str = ""
    part_label: Optional[str] = None  # e.g. "a"
    context_latex: str = ""
    final_answers_latex: tuple[str, ...] = ()
    explanation_text: str = ""


class WorksheetReading(Frozen):
    items: tuple[WorksheetItem, ...]
    notes: str = ""
    shared_context: str = ""  # setup text before the parts, such as v(t) = 1 - e^{-t}


def join_statement(context: str, statement: str) -> str:
    """The shared setup followed by a part's own question. Without a setup it is the statement."""
    setup = context.strip()
    return f"{setup} {statement}" if setup else statement


def full_statement(item: WorksheetItem) -> str:
    """What every solve, judge, and SymPy task receives: the shared setup plus the part's question."""
    return join_statement(item.context_latex, item.statement_latex)


class Grade(Frozen):
    verdict: Verdict
    method: GradeMethod
    label: str  # always GRADE_LABELS[method]
    reference_answer_latex: Optional[str] = None
    explanation: str = ""  # one or two plain sentences
    bank_topic: Optional[str] = None  # set only when method == "bank_key"
    bank_id: Optional[str] = None


class GradedItem(Frozen):
    item: WorksheetItem
    grade: Grade
    regraded: bool = False
    changed_on_regrade: bool = False


class TopicSkill(Frozen):
    topic: str
    title: str
    course: str
    unit: str
    correct: int
    incorrect: int
    unsure: int
    status: SkillStatus
    verified_marks: int  # how many of its marks were method == "bank_key"


class Recommendation(Frozen):
    rank: int
    topic: str
    title: str
    status: SkillStatus
    reason: str  # plain words, cites the marks that caused it
    suggested_level: int  # 1 to 4
    echo_checked: bool  # True only when the topic's gate is enabled
