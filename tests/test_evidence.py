"""Tests for core/evidence.py and how grading evidence reaches a student through Ask Echo and the tutor.

Offline only: model calls are replaced by recording fakes. The properties checked here are behavioral (what a
student can and cannot be told, and how help progresses), not the exact wording of any generated sentence.
"""

import itertools
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import ask, tutor  # noqa: E402
from core.ask import AskReply, RowContext  # noqa: E402
from core.evidence import (  # noqa: E402
    LIKELY_METHODS,
    UNAVAILABLE_REASONS,
    VERIFIED_METHODS,
    asks_for_solution,
    asks_how_checked,
    attempt_stance,
    help_level,
    is_confirmed,
    leaks_internals,
    stance_of,
    verification_of,
)
from core.ladder import Rungs  # noqa: E402
from core.solvers import FakeSolver  # noqa: E402
from core.tutor import TutorReply  # noqa: E402
from core.worksheet import grade_item  # noqa: E402
from core.worksheet_types import Grade, WorksheetItem  # noqa: E402

METHODS = ("bank_key", "sympy_computed", "ai_ladder", "ai_solve_sympy", "ai_judgment", "not_graded")
VERDICTS = ("correct", "incorrect", "unsure")
REASONS = (None, "reading", "format", "disagreement", "no_verdict", "rule")
# The sentence from the bug report, and the vocabulary it leaked.
BUG_REPORT_REPLY = (
    "This answer was marked incorrect, but it was not checked by a verification tool; an AI judged it from the "
    "problem statement alone. The record notes that the student's slope value could not be checked by SymPy."
)
UNSUPPORTED = "Differentiate the test function q(x) = x squared plus 2x."


# ---------------------------------------------------------------------------
# Verification is separate from correctness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, verdict, reason, verification, stance",
    [
        ("bank_key", "correct", None, "verified", "confirmed_correct"),
        ("sympy_computed", "incorrect", None, "verified", "confirmed_incorrect"),
        ("ai_ladder", "incorrect", None, "unverified", "likely_incorrect"),
        ("ai_solve_sympy", "correct", None, "unverified", "likely_correct"),
        # The bug report: a single AI judge, reached because no program could compare the answer.
        ("ai_judgment", "incorrect", None, "unverified", "unknown"),
        ("ai_judgment", "correct", None, "unverified", "unknown"),
        ("ai_ladder", "unsure", "disagreement", "unverified", "unknown"),
        ("ai_judgment", "unsure", "format", "unverified", "unknown"),
        ("sympy_computed", "unsure", "rule", "unverified", "unknown"),
        ("ai_judgment", "unsure", "no_verdict", "unavailable", "unknown"),
        ("not_graded", "unsure", "reading", "unavailable", "unknown"),
    ],
)
def test_verification_and_stance_for_each_kind_of_mark(method, verdict, reason, verification, stance):
    assert verification_of(method, verdict, reason) == verification
    assert stance_of(method, verdict, reason) == stance


def test_a_mark_that_was_not_verified_is_never_confirmed_incorrect():
    """Across every combination of method, verdict and reason: failing to verify never becomes 'wrong'."""
    for method, verdict, reason in itertools.product(METHODS, VERDICTS, REASONS):
        stance = stance_of(method, verdict, reason)
        if verification_of(method, verdict, reason) != "verified":
            assert not is_confirmed(stance), (method, verdict, reason)
        if method not in VERIFIED_METHODS:
            assert stance != "confirmed_incorrect"
        if stance == "confirmed_incorrect":
            assert method in VERIFIED_METHODS and verdict == "incorrect"


def test_technical_failures_are_reported_as_unavailable_not_as_a_judgment():
    for reason in UNAVAILABLE_REASONS:
        assert verification_of("ai_judgment", "unsure", reason) == "unavailable"
        assert stance_of("ai_judgment", "unsure", reason) == "unknown"


def test_the_method_lists_do_not_overlap():
    assert not set(VERIFIED_METHODS) & set(LIKELY_METHODS)


@pytest.mark.parametrize(
    "verdict, stance",
    [("correct", "confirmed_correct"), ("incorrect", "confirmed_incorrect"),
     ("unsure", "unknown"), ("unable_to_verify", "unknown")],
)
def test_practice_check_verdicts_map_to_stances(verdict, stance):
    assert attempt_stance(verdict) == stance


def grade(**fields) -> Grade:
    base = {"verdict": "incorrect", "method": "ai_judgment", "label": "AI-graded"}
    return Grade(**{**base, **fields})


def test_a_stored_grade_carries_its_verification_status_without_changing_its_verdict():
    stored = grade(explanation="The student's answer 1/7 could not be checked by SymPy, so the AI judge marked it incorrect.")

    assert stored.verdict == "incorrect"  # the record stays accurate: what was found, and how it was found
    assert stored.verification == "unverified"
    assert stored.model_dump()["verification"] == "unverified"


def test_saved_grades_without_the_field_still_load_and_get_one():
    saved = {"verdict": "correct", "method": "bank_key", "label": "Marked against a verified bank answer"}

    assert Grade.model_validate(saved).verification == "verified"


def test_a_grade_sent_back_by_the_page_with_the_field_still_loads():
    sent_back = grade().model_dump()

    assert Grade.model_validate(sent_back) == grade()


def test_the_real_grader_stores_an_ai_only_incorrect_as_unverified():
    """A failed program check falls to a single AI judge. The grade says so, and the tutor is not told 'wrong'."""
    item = WorksheetItem(number=1, statement_latex=UNSUPPORTED, student_answer_latex="x")

    stored = grade_item(item, Rungs(*[FakeSolver(verdict="incorrect")] * 3))

    assert (stored.method, stored.verdict) == ("ai_judgment", "incorrect")
    assert stored.verification == "unverified"
    assert stance_of(stored.method, stored.verdict, stored.reason) == "unknown"


# ---------------------------------------------------------------------------
# Help level: Socratic first, then more specific, then the solution
# ---------------------------------------------------------------------------


def test_help_level_grows_with_rounds():
    levels = [help_level("help me with this", rounds) for rounds in range(7)]

    assert levels == ["ask", "hint", "hint", "step", "step", "solution", "solution"]


@pytest.mark.parametrize("message", ["Just show me the full solution", "give me the answer", "I want the working", "solve it for me"])
def test_asking_for_the_solution_gets_it_on_the_first_turn(message):
    assert asks_for_solution(message)
    assert help_level(message, 0) == "solution"


@pytest.mark.parametrize("message", ["Show me a worked example.", "show a worked example", "Can you give me an example?"])
def test_asking_for_an_example_gets_one_not_another_question(message):
    assert help_level(message, 0) == "solution"


def test_the_explain_chips_are_not_answered_with_only_a_question():
    for message in ("Explain the main idea of this topic.", "Explain the idea behind this problem."):
        assert tutor.chat(message, [], CONTEXT, "fake")["help_level"] == "hint"


def test_asking_for_a_hint_skips_the_opening_question():
    assert help_level("I'm stuck, can I get a hint?", 0) == "hint"


@pytest.mark.parametrize("message", ["How was this checked?", "who verified this", "why is this marked incorrect?"])
def test_questions_about_how_a_mark_was_made_are_recognized(message):
    assert asks_how_checked(message)


def test_ordinary_questions_are_not_mistaken_for_how_checked():
    assert not asks_how_checked("How do I differentiate this?")


# ---------------------------------------------------------------------------
# Internal vocabulary never reaches a student unprompted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [BUG_REPORT_REPLY, "SymPy failed to parse it.", "The grading record says so.", "It was not verified.",
     "The ai_judgment method was used.", "The AI judge was unsure.", "See the stack trace."],
)
def test_internal_grading_language_is_caught(text):
    assert leaks_internals(text)


@pytest.mark.parametrize(
    "text",
    ["Let's check your derivative. What is dx/dt at t = 1?", "I can't tell yet whether that slope is right.",
     "Try rewriting the expression with a common denominator."],
)
def test_ordinary_tutoring_language_passes(text):
    assert not leaks_internals(text)


def test_method_talk_is_allowed_only_when_the_student_asked():
    assert leaks_internals("A program called SymPy compared them.")
    assert not leaks_internals("A program called SymPy compared them.", allow_method_talk=True)


# ---------------------------------------------------------------------------
# Ask Echo: the reported scenario, end to end
# ---------------------------------------------------------------------------

JUDGE_ROW = dict(
    statement_latex="Find the slope of the tangent line when t = 1.",
    student_answer_latex="\\frac{1}{7}",
    reference_answer_latex="",
    method="ai_judgment",
    verdict="incorrect",
    reason="",
    explanation="The student's answer \\frac{1}{7} could not be checked by SymPy, so the AI judge marked it incorrect from the statement alone.",
    label="AI-graded: AI judgment only. Not verified by Echo",
)


class RecordingModel:
    """Replaces core.solvers.call_model in either module and records every prompt."""

    def __init__(self, reply):
        self.reply = reply
        self.prompts: list[str] = []

    def __call__(self, model, effort, system, content, schema):
        self.prompts.append(content)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply, None


def row(**overrides) -> RowContext:
    return RowContext(**{**JUDGE_ROW, **overrides})


def test_ask_never_sends_the_grading_records_sentences_to_the_model(monkeypatch):
    model = RecordingModel(AskReply(answer="What is dx/dt at t = 1?"))
    monkeypatch.setattr(ask, "call_model", model)

    ask.answer("Why is my answer wrong?", row(), "live")

    prompt = model.prompts[0]
    for record_text in (JUDGE_ROW["explanation"], JUDGE_ROW["label"], "SymPy", "AI judge", "ai_judgment"):
        assert record_text not in prompt


def test_ask_tells_the_model_an_unverified_incorrect_mark_is_not_known_to_be_wrong(monkeypatch):
    model = RecordingModel(AskReply(answer="What is dx/dt at t = 1?"))
    monkeypatch.setattr(ask, "call_model", model)

    ask.answer("What did I do wrong?", row(), "live")

    prompt = model.prompts[0]
    assert "It is not known whether the answer is right. Do not say it is right or wrong." in prompt
    assert "confirmed incorrect" not in prompt


def test_ask_gives_a_confirmed_wrong_answer_the_reference_but_only_as_checked(monkeypatch):
    model = RecordingModel(AskReply(answer="Which rule did you use first?"))
    monkeypatch.setattr(ask, "call_model", model)

    ask.answer("help", row(method="sympy_computed", reference_answer_latex="2x"), "live")
    ask.answer("help", row(method="ai_ladder", reference_answer_latex="2x"), "live")

    assert "Checked reference answer: 2x" in model.prompts[0]
    assert "Checked reference answer" not in model.prompts[1]
    assert "Unchecked suggestion" in model.prompts[1]


def test_ask_reply_that_repeats_the_bug_report_is_replaced(monkeypatch):
    monkeypatch.setattr(ask, "call_model", RecordingModel(AskReply(answer=BUG_REPORT_REPLY)))

    text = ask.answer("What did I do wrong?", row(), "live")

    assert text == ask.SCRIPTED_BY_STANCE["unknown"]
    assert not leaks_internals(text)


def test_every_offline_ask_reply_is_free_of_grading_language_and_never_claims_wrong_without_evidence():
    for method, verdict, reason in itertools.product(METHODS, VERDICTS, REASONS):
        reply = ask.answer("What did I do wrong?", row(method=method, verdict=verdict, reason=reason or ""), "fake")
        assert not leaks_internals(reply), (method, verdict, reason, reply)
        if not is_confirmed(stance_of(method, verdict, reason)):
            assert not re.search(r"\b(?:wrong|incorrect|mistake)\b", reply, re.IGNORECASE), reply


def test_offline_ask_says_plainly_when_it_cannot_tell():
    reply = ask.answer("What did I do wrong?", row(), "fake")

    assert "cannot confidently tell" in reply and reply.rstrip().endswith("?")


def test_a_technical_problem_is_explained_without_naming_a_tool():
    reply = ask.answer("help", row(method="ai_ladder", verdict="unsure", reason="no_verdict"), "fake")

    assert "technical problem" in reply and not leaks_internals(reply)


def test_a_service_outage_gives_a_plain_message_and_the_cause_is_logged(monkeypatch, caplog):
    from core.solvers import SourceError

    monkeypatch.setattr(ask, "call_model", RecordingModel(SourceError("the model service returned HTTP 503")))

    with pytest.raises(ask.AskError) as caught:
        ask.answer("help", row(), "live")

    assert str(caught.value) == ask.UNAVAILABLE_MESSAGE
    assert "503" not in str(caught.value) and "503" in caplog.text


def test_asking_how_it_was_checked_may_describe_the_method_in_plain_words(monkeypatch):
    model = RecordingModel(AskReply(answer="A math program compared it, but that comparison could not confirm the answer."))
    monkeypatch.setattr(ask, "call_model", model)

    text = ask.answer("How was this checked?", row(), "live")

    assert "How it was checked: not verified: an AI judged the answer on its own" in model.prompts[0]
    assert text.startswith("A math program")


# ---------------------------------------------------------------------------
# Tutor: stance, hint progression across turns, and graceful failures
# ---------------------------------------------------------------------------

CONTEXT = {"topic": "chain_rule", "topic_title": "Chain rule", "level": 2,
           "problem": {"problem_id": "", "statement": "Find the slope when $t=1$.", "origin": "echo"}}


def tutor_prompt(monkeypatch, **context) -> str:
    model = RecordingModel(TutorReply(reply="What is dx/dt at t = 1?"))
    monkeypatch.setattr(tutor, "call_model", model)
    tutor.chat("Is my slope right?", [], {**CONTEXT, **context}, "live")
    return model.prompts[0]


def test_an_attempt_that_could_not_be_verified_is_not_described_as_wrong(monkeypatch):
    prompt = tutor_prompt(monkeypatch, attempts=[{"answer_latex": "1/7", "verdict": "unable_to_verify"}])

    assert "(not confirmed either way)" in prompt
    assert "(incorrect)" not in prompt and "confirmed incorrect" not in prompt


def test_a_checked_wrong_attempt_is_described_as_confirmed(monkeypatch):
    prompt = tutor_prompt(monkeypatch, attempts=[{"answer_latex": "1/9", "verdict": "incorrect"}])

    assert "(confirmed incorrect)" in prompt


def test_the_tutor_prompt_carries_the_help_level(monkeypatch):
    assert "Help level for this reply: ask." in tutor_prompt(monkeypatch)


def test_the_first_tutor_turn_asks_and_does_not_give_the_answer():
    result = tutor.chat("Is my slope right?", [], CONTEXT, "fake")

    assert result["help_level"] == "ask"
    assert result["reply"].rstrip().endswith("?")
    assert "1. " not in result["reply"]


def test_a_stuck_student_is_offered_the_full_solution():
    stuck = [t for _ in range(3) for t in ({"role": "student", "text": "hm"}, {"role": "tutor", "text": "Try again."})]

    result = tutor.chat("I still don't get it", stuck, CONTEXT, "fake")

    assert result["help_level"] == "step"
    assert "show_solution" in [action["id"] for action in result["actions"]]


def test_a_student_who_asks_for_the_solution_gets_it_without_a_hint_ladder():
    result = tutor.chat("Please show me the full solution", [], CONTEXT, "fake")

    assert result["help_level"] == "solution"


def test_hint_requests_and_attempts_count_as_rounds():
    context = {**CONTEXT, "hints_shown": 1, "attempts": [{"answer_latex": "1", "verdict": "incorrect"}]}

    assert tutor.chat("again", [], context, "fake")["help_level"] == "hint"


def test_a_verification_failure_in_practice_does_not_count_as_a_wrong_attempt():
    context = {**CONTEXT, "attempts": [{"answer_latex": "1/7", "verdict": "unable_to_verify"}] * 3}

    assert tutor.chat("again", [], context, "fake")["help_level"] == "ask"


@pytest.mark.parametrize("leaky", [BUG_REPORT_REPLY, "SymPy could not check it.", "The AI judge is unsure."])
def test_a_tutor_reply_with_grading_language_is_replaced_by_guided_questions(monkeypatch, leaky):
    monkeypatch.setattr(tutor, "call_model", RecordingModel(TutorReply(reply=leaky)))

    result = tutor.chat("Is my slope right?", [], CONTEXT, "live")

    assert result["status"] == "ok" and result["engine"] == "scripted"
    assert not leaks_internals(result["reply"])


def test_a_tutor_service_outage_gives_a_plain_message_with_no_internals(monkeypatch):
    from core.solvers import SourceError

    monkeypatch.setattr(tutor, "call_model", RecordingModel(SourceError("API key missing or invalid")))

    result = tutor.chat("hello", [], CONTEXT, "live")

    assert result == {"status": "error", "error": tutor.UNAVAILABLE_MESSAGE}
    assert not leaks_internals(result["error"]) and "key" not in result["error"].lower()
