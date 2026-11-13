"""Read a worksheet photo into problems and the student's answers, then grade each answer.

Reading follows core/photo_reader.py: LiveWorksheetSource (Claude vision),
ReplayWorksheetSource (a saved reading matched by image SHA-256; the image is never
saved), and FakeWorksheetSource (scripted). read_worksheet() checks the image bytes
before any source runs and never raises for a source failure.

Grading tries these in order. bank_key: the statement matches an eligible bank problem, and the
student's answer is compared with the verified key by SymPy. sympy_computed: a derivative or limit
statement is computed by SymPy (core/sympy_task.py) with one blind AI cross-check. ai_ladder: Haiku
and Sonnet solve blind and Opus breaks a tie (core/ladder.py). ai_judgment: a model judges the
written answer when neither answer can be read by SymPy. Every answer is read by core.latex_reader
only.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic  # noqa: F401 - tests patch worksheet.anthropic.Anthropic
from core.bank_fallback import BANK_PATH
from core.drafter import DEFAULT_EFFORT, DEFAULT_MODEL, SOURCE_FAKE, SOURCE_LIVE
from core.ladder import (  # noqa: F401 - REGRADE_EFFORT and Rungs are re-exported
    REGRADE_EFFORT,
    Rungs,
    as_rungs,
    grade_unmatched,
    regrade_mark,
)
from core.photo_reader import SHA256_HEX_PATTERN, bank_topic_ids, check_image, sha256_hex
from core.sympy_task import strip_label
from core.solvers import (  # noqa: F401 - re-exported for callers and tests
    CONSTANT_EXPLANATION,
    JUDGE_FAILED_EXPLANATION,
    UNCOMPARED_EXPLANATION,
    WHY_FORMAT,
    WHY_READING,
    AnswerSolver,
    CallBudget,
    CallLedger,
    FakeSolver,
    LiveSolver,
    Mark,
    Question,
    SourceError,
    answers_equivalent,
    call_model,
    compare_answers,
    comparison_mark,
)
from core.worksheet_types import (
    GRADE_LABELS,
    Grade,
    GradedItem,
    GradeMethod,
    WorksheetItem,
    WorksheetReading,
)
from scripts.audit_bank import classify, load_bank

MAX_ITEMS = 20
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_UNREADABLE = "unreadable"
READING_SOURCES = (SOURCE_LIVE, SOURCE_FAKE)
BANK_METHOD: GradeMethod = "bank_key"
SYMPY_METHOD: GradeMethod = "sympy_computed"
JUDGE_METHOD: GradeMethod = "ai_judgment"
DETERMINISTIC_METHODS = (BANK_METHOD, SYMPY_METHOD)
NO_ANSWER_EXPLANATION = "no answer written"
NOT_GRADED_METHOD: GradeMethod = "not_graded"
LOW_CONFIDENCE_EXPLANATION = (
    "The writing for this part was faint or unclear, so Echo did not mark it. "
    "Compare the reading with the photo, then try a clearer photo."
)
DIFFERENT_PHOTO_MESSAGE = "saved reading is for a different photo"
UNREADABLE_MESSAGE = "no problems were read from the worksheet"
ITEM_CAP_NOTE = "the worksheet has {total} problems; only the first {kept} were kept"
BLANK_DROPPED_NOTE = "{count} blank problem(s) dropped"
TOPIC_CLEARED_NOTE = "topic guess {guess!r} is not a bank topic, so it was cleared"

WORKSHEET_SYSTEM_PROMPT = (
    "You transcribe a student's handwritten or printed calculus worksheet for Echo. "
    "Put any shared setup that comes before the parts, such as definitions like v(t) = ..., in "
    "shared_context, exactly as written. For every lettered or numbered part, write statement_latex "
    "with only that part's own question, exactly as written. Write final_answers_latex as the "
    "student's final mathematical answers only, in order, as bare math with no words and no units, "
    "for example v'(t) = e^{-t} and then v'(0) = 1. Write the student's written sentence in "
    "explanation_text. Working steps may stay in student_answer_latex, or null when no answer is "
    "written. Do not solve, simplify, complete, or correct anything, even when it is wrong. If any "
    "part is illegible, cut off, faint, smudged, or ambiguous, or you had to guess a character, say "
    "which part in notes and set that part's confidence to low. Choose "
    "topic_guess only from the topic ids given in the request, or null if none fits. Return only "
    "the structured output requested."
)
DRONE_CONTEXT = "A drone has velocity v(t) = 1 - e^{-t}."


# The scripted drone worksheet: shared setup, then parts a, b, and c. Used by fake mode.
FAKE_READING = WorksheetReading(
    shared_context=DRONE_CONTEXT,
    items=(
        WorksheetItem(
            number=1,
            part_label="a",
            statement_latex="Compute $v(0)$.",
            student_answer_latex="v(0) = 1 - e^{0} = 0. The drone starts at rest.",
            final_answers_latex=("v(0) = 0",),
            explanation_text="The drone starts at rest.",
            confidence="high",
        ),
        WorksheetItem(
            number=2,
            part_label="b",
            statement_latex="Compute $\\int_0^5 v(t)\\,dt$.",
            student_answer_latex="\\int_0^5 v(t)\\,dt = 6 - e^{5}. The total distance is 6 - e^{5}.",
            final_answers_latex=("6 - e^{5}",),
            explanation_text="The total distance is 6 - e^{5}.",
            confidence="high",
        ),
        WorksheetItem(
            number=3,
            part_label="c",
            statement_latex="Find $v'(t)$. Compute $v'(0)$.",
            student_answer_latex="v'(t) = e^{-t}, so v'(0) = 1. The acceleration starts at 1.",
            final_answers_latex=("v'(t) = e^{-t}", "v'(0) = 1"),
            explanation_text="The acceleration starts at 1.",
            confidence="high",
        ),
    ),
    notes="scripted reading; no model read this photo",
)


# ---------------------------------------------------------------------------
# Reading sources
# ---------------------------------------------------------------------------


class WorksheetSource:
    """Base for worksheet sources. source is "live" or "fake"; name is for display."""

    name: str = "source"
    source: str = ""
    last_usage: Optional[dict] = None

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        raise NotImplementedError


class FakeWorksheetSource(WorksheetSource):
    name = "fake"
    source = SOURCE_FAKE

    def __init__(self, reading: WorksheetReading = FAKE_READING) -> None:
        self._reading = reading

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        return self._reading


class ReplayWorksheetSource(WorksheetSource):
    """Plays back a saved reading for the same photo. The original source is exposed as source."""

    def __init__(self, path: Path | str) -> None:
        saved = load_worksheet_reading(path)
        self._saved = saved
        self.source = saved["source"]
        self.saved_at = saved.get("saved_at", "unknown time")
        self.name = f"replay (saved {self.source} reading)"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        if sha256_hex(image) != self._saved["image_sha256"]:
            raise SourceError(DIFFERENT_PHOTO_MESSAGE)
        return self._saved["reading"]


class LiveWorksheetSource(WorksheetSource):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def get_reading(
        self, image: bytes, media_type: str, topics: tuple[str, ...]
    ) -> WorksheetReading:
        content = _image_content(image, media_type, build_worksheet_prompt(topics))
        reading, self.last_usage = call_model(
            self.model, self.effort, WORKSHEET_SYSTEM_PROMPT, content, WorksheetReading
        )
        return reading


def _image_content(image: bytes, media_type: str, prompt: str) -> list[dict]:
    """The image block comes before the text block, as the vision API expects."""
    encoded = base64.standard_b64encode(image).decode("ascii")
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        },
        {"type": "text", "text": prompt},
    ]


def build_worksheet_prompt(topics: tuple[str, ...]) -> str:
    return "\n".join(
        [
            "Transcribe every numbered problem on the worksheet in the photo, "
            "with the student's written answer to each.",
            "topic_guess must be one of these topic ids, or null: " + ", ".join(topics),
        ]
    )


# ---------------------------------------------------------------------------
# Reading the worksheet
# ---------------------------------------------------------------------------


def _digest(image: object) -> Optional[str]:
    if not isinstance(image, (bytes, bytearray)):
        return None
    return sha256_hex(bytes(image))


def _tokens(source: WorksheetSource) -> Optional[dict]:
    usage = getattr(source, "last_usage", None)
    return dict(usage) if usage else None


def _join_notes(existing: str, extra: str) -> str:
    return " ".join(part for part in (existing.strip(), extra) if part)


def _topic_ids(topics: Optional[Sequence[str]]) -> tuple[str, ...]:
    if topics is None:
        return bank_topic_ids()
    return tuple(sorted(set(topics)))


def _final_answers(item: WorksheetItem) -> tuple[str, ...]:
    return tuple(part.strip() for part in item.final_answers_latex if part.strip())


def _normalized_item(item: WorksheetItem, topics: tuple[str, ...], context: str) -> WorksheetItem:
    """Strip the text, make a blank answer None, copy in the shared setup, and clear a topic guess that is not a bank topic."""
    answer = (item.student_answer_latex or "").strip() or None
    update: dict = {
        "statement_latex": item.statement_latex.strip(),
        "student_answer_latex": answer,
        "context_latex": context,
        "final_answers_latex": _final_answers(item),
        "explanation_text": item.explanation_text.strip(),
        "part_label": (item.part_label or "").strip() or None,
    }
    if item.topic_guess is not None and item.topic_guess not in topics:
        update["topic_guess"] = None
        update["notes"] = _join_notes(item.notes, TOPIC_CLEARED_NOTE.format(guess=item.topic_guess))
    return item.model_copy(update=update)


def _normalized(reading: WorksheetReading, topics: tuple[str, ...]) -> WorksheetReading:
    """Drop blank problems, copy the shared setup into every part, keep the first MAX_ITEMS, and record each change."""
    context = reading.shared_context.strip()
    usable = [
        _normalized_item(item, topics, context)
        for item in reading.items
        if item.statement_latex.strip()
    ]
    notes = reading.notes
    dropped = len(reading.items) - len(usable)
    if dropped:
        notes = _join_notes(notes, BLANK_DROPPED_NOTE.format(count=dropped))
    if len(usable) > MAX_ITEMS:
        notes = _join_notes(notes, ITEM_CAP_NOTE.format(total=len(usable), kept=MAX_ITEMS))
        usable = usable[:MAX_ITEMS]
    update = {"items": tuple(usable), "notes": notes, "shared_context": context}
    return reading.model_copy(update=update)


def _result(
    status: str,
    source_name: str,
    digest: Optional[str],
    error: Optional[str] = None,
    reading: Optional[WorksheetReading] = None,
    tokens: Optional[dict] = None,
) -> dict:
    return {
        "status": status,
        "source": source_name,
        "reading": reading.model_dump(mode="json") if reading is not None else None,
        "image_sha256": digest,
        "error": error,
        "tokens": tokens,
    }


def read_worksheet(
    image: bytes, source: WorksheetSource, topics: Optional[Sequence[str]] = None
) -> dict:
    """Read a worksheet photo with source. Never raises for bad input or source failures."""
    digest = _digest(image)
    media_type, image_error = check_image(image)
    if image_error is not None:
        return _result(STATUS_ERROR, source.name, digest, error=image_error)
    try:
        allowed = _topic_ids(topics)
        raw = WorksheetReading.model_validate(
            source.get_reading(bytes(image), media_type, allowed)
        )
    except Exception as error:  # a reading-source failure must not crash the caller
        return _result(STATUS_ERROR, source.name, digest, error=str(error) or type(error).__name__)
    reading = _normalized(raw, allowed)
    if not reading.items:
        return _result(
            STATUS_UNREADABLE, source.name, digest, error=UNREADABLE_MESSAGE,
            reading=reading, tokens=_tokens(source),
        )
    return _result(STATUS_OK, source.name, digest, reading=reading, tokens=_tokens(source))


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and SHA256_HEX_PATTERN.fullmatch(value) is not None


def save_worksheet_reading(
    path: Path | str, image_sha256: str, reading: WorksheetReading, source: str
) -> None:
    """Write a reading to a JSON file. The image itself is never written."""
    if source not in READING_SOURCES:
        raise ValueError(f"source must be one of {READING_SOURCES}, got {source!r}")
    if not _is_sha256_hex(image_sha256):
        raise ValueError("image_sha256 must be a 64-character lowercase hex digest")
    payload = {
        "source": source,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "image_sha256": image_sha256,
        "reading": reading.model_dump(mode="json"),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_worksheet_reading(path: Path | str) -> dict:
    """Read a saved reading. Raises ValueError when the file is not a valid saved reading."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("source") not in READING_SOURCES:
        raise ValueError(f"{path} is not a saved Echo worksheet reading")
    if not _is_sha256_hex(data.get("image_sha256")):
        raise ValueError(f"{path} is missing its image_sha256")
    if not isinstance(data.get("reading"), dict):
        raise ValueError(f"{path} is missing its reading")
    reading = WorksheetReading.model_validate(data["reading"])
    return {**data, "reading": reading}


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _statement_key(text: str) -> str:
    """Normalized statement for bank matching: no $ signs, no \\displaystyle, no whitespace."""
    return "".join(text.replace("$", "").replace("\\displaystyle", "").split())


def _eligible_bank() -> tuple[dict, ...]:
    """Bank problems that pass the audit. Raises ValueError when the bank cannot be read."""
    return tuple(problem for problem in load_bank(BANK_PATH) if classify(problem) is None)


def _bank_match(item: WorksheetItem, problems: tuple[dict, ...]) -> Optional[dict]:
    key = _statement_key(item.statement_latex)
    matches = [
        problem
        for problem in problems
        if _statement_key(problem["statement"]) == key
        and (item.topic_guess is None or problem["topic"] == item.topic_guess)
    ]
    if not matches:
        return None
    return min(matches, key=lambda problem: (problem["topic"], str(problem["id"])))


def _reference_latex(problem: dict) -> str:
    return str((problem.get("answer") or {}).get("latex", ""))


def _answer_text(item: WorksheetItem) -> Optional[str]:
    text = (item.student_answer_latex or "").strip()
    return text or None


def _question(item: WorksheetItem) -> Optional[Question]:
    """The part as graders see it, or None when the student wrote nothing.

    The final answers are compared; the full written line is only ever shown to the judge.
    """
    working = _answer_text(item) or ""
    answers = tuple(strip_label(answer) for answer in _final_answers(item)) or ((working,) if working else ())
    if not answers:
        return None
    return Question(item.statement_latex, item.context_latex, answers, working)


def _grade_from_mark(mark: Mark, bank_problem: Optional[dict] = None) -> Grade:
    """The grade for a mark. Only an unsure mark carries a reason, so a correct or incorrect grade has none."""
    is_unsure = mark.verdict == "unsure"
    return Grade(
        verdict=mark.verdict,
        method=mark.method,
        label=GRADE_LABELS[mark.method],
        reference_answer_latex=mark.reference,
        explanation=mark.explanation,
        bank_topic=bank_problem["topic"] if bank_problem is not None else None,
        bank_id=str(bank_problem["id"]) if bank_problem is not None else None,
        reason=mark.reason if is_unsure else None,
    )


def _bank_grade(problem: dict, student: str) -> Grade:
    reference = _reference_latex(problem)
    mark = comparison_mark(
        compare_answers(reference, student), student, reference, BANK_METHOD, "the verified key"
    )
    if mark is None:
        mark = Mark("unsure", BANK_METHOD, UNCOMPARED_EXPLANATION, reference, WHY_FORMAT)
    return _grade_from_mark(mark, problem)


def _no_answer_grade(problem: Optional[dict]) -> Grade:
    if problem is None:
        return _grade_from_mark(Mark("unsure", JUDGE_METHOD, NO_ANSWER_EXPLANATION, reason=WHY_READING))
    return _grade_from_mark(
        Mark("unsure", BANK_METHOD, NO_ANSWER_EXPLANATION, _reference_latex(problem), WHY_READING),
        problem,
    )


def bank_match_grade(item: WorksheetItem, bank: Sequence[dict]) -> Optional[Grade]:
    """The bank_key grade for an item that matches an eligible bank problem, else None.

    Runs no SymPy computation and no model call, so replay can grade bank matches cheaply.
    """
    problem = _bank_match(item, tuple(bank))
    if problem is None:
        return None
    question = _question(item)
    if question is None:
        return _no_answer_grade(problem)
    return _bank_grade(problem, question.compared)


def grade_item(
    item: WorksheetItem,
    rungs: Rungs | AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
    effort: Optional[str] = None,
    budget: Optional[CallBudget] = None,
) -> Grade:
    """Grade one item: bank_key, then sympy_computed or ai_ladder, then ai_judgment.

    A single solver is used for every rung. Never raises for a solver failure.
    """
    if item.confidence == "low":  # a misread part must never earn a verified-looking mark
        return _grade_from_mark(
            Mark("unsure", NOT_GRADED_METHOD, LOW_CONFIDENCE_EXPLANATION, reason=WHY_READING)
        )
    problems = _eligible_bank() if bank is None else tuple(bank)
    problem = _bank_match(item, problems)
    question = _question(item)
    if question is None:
        return _no_answer_grade(problem)
    if problem is not None:
        return _bank_grade(problem, question.compared)
    ledger = CallLedger(budget if budget is not None else CallBudget())
    mark = grade_unmatched(question, as_rungs(rungs), ledger, effort)
    return _grade_from_mark(mark)


def grade_worksheet(
    reading: WorksheetReading,
    rungs: Rungs | AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
) -> list[GradedItem]:
    """Grade every item. The whole worksheet shares one call budget."""
    problems = _eligible_bank() if bank is None else tuple(bank)
    budget = CallBudget()
    return [
        GradedItem(item=item, grade=grade_item(item, rungs, bank=problems, budget=budget))
        for item in reading.items
    ]


def _regraded_grade(graded: GradedItem, rungs: Rungs, problems: tuple[dict, ...]) -> Grade:
    item = graded.item
    question = _question(item)
    if graded.grade.method in (SYMPY_METHOD, NOT_GRADED_METHOD):
        # The cross-check outcome cannot be re-derived without an AI call, and an unclear reading
        # is not fixed by grading again, so the mark is kept.
        return graded.grade
    if graded.grade.method == BANK_METHOD or question is None:
        return grade_item(item, rungs, bank=problems)
    return _grade_from_mark(regrade_mark(question, rungs))


def regrade_item(
    graded: GradedItem,
    rungs: Rungs | AnswerSolver,
    bank: Optional[Sequence[dict]] = None,
) -> GradedItem:
    """Grade again. bank_key and sympy_computed never change; AI grades get one fresh Sonnet solve."""
    problems = _eligible_bank() if bank is None else tuple(bank)
    fresh = _regraded_grade(graded, as_rungs(rungs), problems)
    is_ai = graded.grade.method not in DETERMINISTIC_METHODS
    changed = is_ai and fresh.verdict != graded.grade.verdict
    return GradedItem(
        item=graded.item,
        grade=fresh,
        regraded=True,
        changed_on_regrade=changed,
    )
