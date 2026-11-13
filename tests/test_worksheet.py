"""Tests for core/worksheet.py. Offline only: fake solvers and fake sources, no network, no API key.

Images are built in the test (a 1x1 PNG), so no files are needed except a temp path for replay.
"""

import base64
import hashlib
import struct
import sys
import zlib
from pathlib import Path

import anthropic
import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import worksheet  # noqa: E402
from core.bank_fallback import BANK_PATH  # noqa: E402
from core.worksheet import (  # noqa: E402
    CONSTANT_EXPLANATION,
    MAX_ITEMS,
    NO_ANSWER_EXPLANATION,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNREADABLE,
    FakeSolver,
    FakeWorksheetSource,
    LiveSolver,
    LiveWorksheetSource,
    ReplayWorksheetSource,
    WorksheetSource,
    answers_equivalent,
    grade_item,
    grade_worksheet,
    load_worksheet_reading,
    read_worksheet,
    regrade_item,
    save_worksheet_reading,
)
from core.worksheet_types import (  # noqa: E402
    GRADE_LABELS,
    GradedItem,
    WorksheetItem,
    WorksheetReading,
)
from scripts.audit_bank import load_bank  # noqa: E402

LA01 = next(problem for problem in load_bank(BANK_PATH) if problem["id"] == "LA01")
LA01_STATEMENT = LA01["statement"]
LA01_ANSWER = LA01["answer"]["latex"]
SOLVER_STATEMENT = "Differentiate the test function q(x) = x squared plus 2x."
CUSTOM_STATEMENT = "Find the derivative of the test polynomial r(x) = x cubed."
SECRET_STUDENT_ANSWER = "7x^{9}+11"


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def make_png(red: int = 255) -> bytes:
    """A valid 1x1 RGB PNG; red sets the pixel colour so two photos differ."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes([0, red, 0, 0]))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", pixel)
        + _chunk(b"IEND", b"")
    )


def item(
    statement: str,
    student: str | None,
    number: int = 1,
    topic: str | None = None,
) -> WorksheetItem:
    return WorksheetItem(
        number=number,
        statement_latex=statement,
        student_answer_latex=student,
        topic_guess=topic,
    )


def reading_of(*items: WorksheetItem, notes: str = "") -> WorksheetReading:
    return WorksheetReading(items=tuple(items), notes=notes)


class CountingSource(FakeWorksheetSource):
    """A fake source that records each call, so tests can prove it was never reached."""

    def __init__(self, reading: WorksheetReading | None = None) -> None:
        super().__init__(reading or reading_of(item(CUSTOM_STATEMENT, "x")))
        self.calls = 0

    def get_reading(self, image, media_type, topics):
        self.calls += 1
        return super().get_reading(image, media_type, topics)


class FakeUsage:
    input_tokens = 11
    output_tokens = 7


class FakeParsedResponse:
    def __init__(self, parsed) -> None:
        self.stop_reason = "end_turn"
        self.parsed_output = parsed
        self.usage = FakeUsage()


class RecordingMessages:
    def __init__(self, parsed) -> None:
        self.requests: list[dict] = []
        self._parsed = parsed

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        return FakeParsedResponse(self._parsed)


class RecordingClient:
    def __init__(self, parsed) -> None:
        self.messages = RecordingMessages(parsed)


def _forbidden_client():
    raise AssertionError("no network client may be built without a key")


# ---------------------------------------------------------------------------
# Tier a: bank_key
# ---------------------------------------------------------------------------


def test_bank_key_correct_answer_matches_verified_key():
    solver = FakeSolver()
    grade = grade_item(item(LA01_STATEMENT, "-\\frac{1}{8}", topic="algebraic"), solver)
    assert grade.verdict == "correct"
    assert grade.method == "bank_key"
    assert grade.label == GRADE_LABELS["bank_key"]
    assert grade.bank_id == "LA01"
    assert grade.bank_topic == "algebraic"
    assert grade.reference_answer_latex == LA01_ANSWER
    assert solver.solve_calls == () and solver.judge_calls == ()


def test_bank_key_wrong_answer_is_incorrect_against_verified_key():
    grade = grade_item(item(LA01_STATEMENT, "\\frac{1}{8}", topic="algebraic"), FakeSolver())
    assert grade.verdict == "incorrect"
    assert grade.method == "bank_key"
    assert grade.label == GRADE_LABELS["bank_key"]
    assert grade.bank_id == "LA01"


def test_bank_match_ignores_dollar_signs_displaystyle_and_spacing():
    plain = "Evaluate \\lim_{x \\to 1} \\frac{- \\frac{1}{2} + \\frac{1}{x + 1}}{x^{2} - 1}. Give an exact answer."
    grade = grade_item(item(plain, "-1/8", topic="algebraic"), FakeSolver())
    assert grade.method == "bank_key"
    assert grade.verdict == "correct"


def test_bank_match_with_wrong_topic_guess_falls_to_sympy_tier():
    grade = grade_item(item(LA01_STATEMENT, "-\\frac{1}{8}", topic="power_rule"), FakeSolver())
    assert grade.method == "sympy_computed"
    assert grade.bank_id is None


def test_bank_key_with_no_answer_is_unsure_and_never_calls_a_model():
    solver = FakeSolver()
    grade = grade_item(item(LA01_STATEMENT, None, topic="algebraic"), solver)
    assert grade.verdict == "unsure"
    assert grade.method == "bank_key"
    assert grade.explanation == NO_ANSWER_EXPLANATION
    assert solver.solve_calls == () and solver.judge_calls == ()


# ---------------------------------------------------------------------------
# SymPy equivalence
# ---------------------------------------------------------------------------


def test_equivalent_forms_of_an_answer_are_equal():
    assert answers_equivalent("x^{2}+2x", "2x+x^{2}") == "equal"


def test_different_functions_are_different():
    assert answers_equivalent("x^{2}+2x", "x^{2}+3x") == "different"


def test_unreadable_answer_is_unknown():
    assert answers_equivalent("x^{2}", "\\int x\\,dx") == "unknown"


def test_constant_only_difference_is_unknown_with_plus_c_reason():
    comparison = worksheet.compare_answers("x^{2}+2x", "x^{2}+2x+3")
    assert comparison.status == "unknown"
    assert comparison.constant_offset is True


def test_two_different_constants_are_different_not_plus_c():
    assert worksheet.compare_answers("-\\frac{1}{8}", "\\frac{1}{8}").status == "different"


# ---------------------------------------------------------------------------
# Tier b: ai_solve_sympy and tier c: ai_judgment
# ---------------------------------------------------------------------------


def test_no_bank_match_with_solver_answer_is_ai_ladder():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"})
    grade = grade_item(item(SOLVER_STATEMENT, "2x+x^{2}"), solver)
    assert grade.verdict == "correct"
    assert grade.method == "ai_ladder"
    assert grade.label == GRADE_LABELS["ai_ladder"]
    assert grade.reference_answer_latex == "x^{2}+2x"
    assert grade.bank_id is None and grade.bank_topic is None


def test_ai_solve_wrong_student_answer_is_incorrect():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"})
    grade = grade_item(item(SOLVER_STATEMENT, "x^{2}"), solver)
    assert grade.verdict == "incorrect"
    assert grade.method == "ai_ladder"


def test_ai_solve_constant_only_difference_is_unsure_with_plus_c_explanation():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"})
    grade = grade_item(item(SOLVER_STATEMENT, "x^{2}+2x+3"), solver)
    assert grade.verdict == "unsure"
    assert grade.method == "ai_ladder"
    assert grade.explanation == CONSTANT_EXPLANATION


def test_unreadable_solver_answer_falls_to_ai_judgment():
    solver = FakeSolver({SOLVER_STATEMENT: "\\int x\\,dx"}, verdict="incorrect")
    grade = grade_item(item(SOLVER_STATEMENT, "x^{2}+2x"), solver)
    assert grade.method == "ai_judgment"
    assert grade.label == GRADE_LABELS["ai_judgment"]
    assert grade.verdict == "incorrect"
    assert len(solver.judge_calls) == 1


def test_unreadable_student_answer_falls_to_ai_judgment():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"}, verdict="correct")
    grade = grade_item(item(SOLVER_STATEMENT, "\\int x\\,dx"), solver)
    assert grade.method == "ai_judgment"
    assert grade.verdict == "correct"


def test_student_answer_without_an_answer_is_unsure_and_no_model_is_called():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"}, verdict="correct")
    grade = grade_item(item(SOLVER_STATEMENT, None), solver)
    assert grade.verdict == "unsure"
    assert grade.explanation == "no answer written"
    assert grade.method == "ai_judgment"
    assert solver.solve_calls == ()
    assert solver.judge_calls == ()


def test_blank_student_answer_counts_as_no_answer():
    solver = FakeSolver()
    grade = grade_item(item(SOLVER_STATEMENT, "   "), solver)
    assert grade.explanation == "no answer written"
    assert solver.solve_calls == ()


def test_solver_never_receives_the_student_answer():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}"})
    grade_item(item(SOLVER_STATEMENT, SECRET_STUDENT_ANSWER), solver)
    # The ladder asks a fast and a mid solve, so the statement is sent twice and never the answer.
    assert solver.solve_calls == ((SOLVER_STATEMENT, None), (SOLVER_STATEMENT, None))
    assert all(SECRET_STUDENT_ANSWER not in str(call) for call in solver.solve_calls)


def test_solver_error_never_crashes_and_falls_to_judgment():
    solver = FakeSolver(error="scripted solver failure", verdict="unsure")
    grade = grade_item(item(SOLVER_STATEMENT, "x^{2}"), solver)
    assert grade.verdict == "unsure"
    assert grade.method == "ai_judgment"
    assert len(solver.judge_calls) == 1


def test_live_solver_without_key_is_unsure_and_builds_no_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(worksheet.anthropic, "Anthropic", _forbidden_client)
    grade = grade_item(item(SOLVER_STATEMENT, "x^{2}"), LiveSolver())
    assert grade.verdict == "unsure"
    assert grade.method == "ai_judgment"
    assert grade.explanation == worksheet.JUDGE_FAILED_EXPLANATION


# ---------------------------------------------------------------------------
# Grading a whole reading
# ---------------------------------------------------------------------------


def test_grade_worksheet_grades_each_item_in_order():
    reading = reading_of(
        item(LA01_STATEMENT, "-\\frac{1}{8}", number=1, topic="algebraic"),
        item(SOLVER_STATEMENT, "2x+x^{2}", number=2),
    )
    graded = grade_worksheet(reading, FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"}))
    assert [entry.item.number for entry in graded] == [1, 2]
    assert [entry.grade.method for entry in graded] == ["bank_key", "ai_ladder"]


# ---------------------------------------------------------------------------
# Regrading
# ---------------------------------------------------------------------------


def test_regrade_of_bank_key_grade_is_unchanged():
    graded = grade_worksheet(
        reading_of(item(LA01_STATEMENT, "-\\frac{1}{8}", topic="algebraic")), FakeSolver()
    )[0]
    regraded = regrade_item(graded, FakeSolver())
    assert regraded.grade.verdict == graded.grade.verdict == "correct"
    assert regraded.regraded is True
    assert regraded.changed_on_regrade is False


def test_regrade_of_ai_grade_with_different_answer_sets_changed():
    first = grade_item(item(SOLVER_STATEMENT, "x^{2}+2x"), FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"}))
    graded = GradedItem(item=item(SOLVER_STATEMENT, "x^{2}+2x"), grade=first)
    second_solver = FakeSolver({SOLVER_STATEMENT: "x^{2}"})
    regraded = regrade_item(graded, second_solver)
    assert graded.grade.verdict == "correct"
    assert regraded.grade.verdict == "incorrect"
    assert regraded.regraded is True
    assert regraded.changed_on_regrade is True
    assert second_solver.solve_calls == ((SOLVER_STATEMENT, worksheet.REGRADE_EFFORT),)


def test_regrade_of_ai_grade_with_same_verdict_is_not_changed():
    solver = FakeSolver({SOLVER_STATEMENT: "x^{2}+2x"})
    first = grade_item(item(SOLVER_STATEMENT, "2x+x^{2}"), solver)
    regraded = regrade_item(GradedItem(item=item(SOLVER_STATEMENT, "2x+x^{2}"), grade=first), solver)
    assert regraded.grade.verdict == "correct"
    assert regraded.changed_on_regrade is False


def test_regrade_does_not_mutate_its_input():
    graded = GradedItem(
        item=item(SOLVER_STATEMENT, "x^{2}+2x"),
        grade=grade_item(item(SOLVER_STATEMENT, "x^{2}+2x"), FakeSolver({SOLVER_STATEMENT: "x^{2}"})),
    )
    before = graded.model_dump()
    regrade_item(graded, FakeSolver({SOLVER_STATEMENT: "x^{2}"}))
    assert graded.model_dump() == before


# ---------------------------------------------------------------------------
# Image checks and reading sources
# ---------------------------------------------------------------------------


def test_non_image_bytes_are_rejected_before_source_call():
    source = CountingSource()
    result = read_worksheet(b"this is a text file, not a photo", source)
    assert result["status"] == STATUS_ERROR
    assert "PNG, JPEG, WEBP, or GIF" in result["error"]
    assert source.calls == 0


def test_fake_source_reads_ok_and_keeps_bank_topic_guess():
    result = read_worksheet(make_png(), FakeWorksheetSource(), topics=["power_rule", "algebraic"])
    assert result["status"] == STATUS_OK
    assert result["source"] == "fake"
    assert result["reading"]["items"][0]["topic_guess"] == "power_rule"
    assert result["image_sha256"] == hashlib.sha256(make_png()).hexdigest()


def test_topic_guess_outside_bank_becomes_none_with_note():
    reading = reading_of(item(SOLVER_STATEMENT, "x^{2}", topic="made_up_topic"))
    result = read_worksheet(make_png(), FakeWorksheetSource(reading), topics=["power_rule"])
    cleaned = result["reading"]["items"][0]
    assert cleaned["topic_guess"] is None
    assert "made_up_topic" in cleaned["notes"]


def test_blank_answer_is_read_as_none():
    reading = reading_of(item(SOLVER_STATEMENT, "   "))
    result = read_worksheet(make_png(), FakeWorksheetSource(reading), topics=["power_rule"])
    assert result["reading"]["items"][0]["student_answer_latex"] is None


def test_worksheet_with_no_problems_is_unreadable():
    result = read_worksheet(make_png(), FakeWorksheetSource(reading_of()), topics=["power_rule"])
    assert result["status"] == STATUS_UNREADABLE
    assert result["error"] == worksheet.UNREADABLE_MESSAGE


def test_item_cap_keeps_the_first_twenty_with_a_note():
    items = tuple(item(f"Find item number {n}.", "x", number=n) for n in range(1, 26))
    result = read_worksheet(make_png(), FakeWorksheetSource(WorksheetReading(items=items)), topics=["power_rule"])
    assert result["status"] == STATUS_OK
    assert len(result["reading"]["items"]) == MAX_ITEMS == 20
    assert result["reading"]["items"][-1]["number"] == 20
    assert "only the first 20 were kept" in result["reading"]["notes"]


def test_source_failure_is_an_error_not_a_crash():
    class BrokenSource(WorksheetSource):
        name = "broken"

        def get_reading(self, image, media_type, topics):
            raise RuntimeError("scripted reading failure")

    result = read_worksheet(make_png(), BrokenSource(), topics=["power_rule"])
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "scripted reading failure"


def test_inputs_are_not_mutated():
    image = bytearray(make_png())
    image_before = bytes(image)
    reading = reading_of(item(SOLVER_STATEMENT, "  x^{2}  ", topic="made_up"))
    dumped_before = reading.model_dump()
    source = FakeWorksheetSource(reading)
    read_worksheet(image, source, ["power_rule"])
    grade_worksheet(reading, FakeSolver())
    assert bytes(image) == image_before
    assert reading.model_dump() == dumped_before
    assert source._reading is reading


# ---------------------------------------------------------------------------
# Live reading request shape and no-key behaviour (no network)
# ---------------------------------------------------------------------------


def test_live_reading_request_puts_image_before_text_and_has_no_sampling(monkeypatch):
    png = make_png()
    client = RecordingClient(reading_of(item(SOLVER_STATEMENT, "x^{2}", topic="power_rule")))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(worksheet.anthropic, "Anthropic", lambda: client)
    result = read_worksheet(png, LiveWorksheetSource(), topics=["power_rule", "algebraic"])
    assert result["status"] == STATUS_OK
    assert result["tokens"] == {"input_tokens": 11, "output_tokens": 7}

    request = client.messages.requests[0]
    content = request["messages"][0]["content"]
    assert [block["type"] for block in content] == ["image", "text"]
    assert content[0]["source"]["data"] == base64.standard_b64encode(png).decode("ascii")
    assert "algebraic, power_rule" in content[1]["text"]  # topic ids are sorted in the prompt
    assert request["output_format"] is WorksheetReading
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & set(request)


def test_live_reading_without_key_is_error_and_no_network(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(worksheet.anthropic, "Anthropic", _forbidden_client)
    result = read_worksheet(make_png(), LiveWorksheetSource(), topics=["power_rule"])
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"


def test_live_auth_failure_is_mapped_to_error(monkeypatch):
    class FailingMessages:
        def parse(self, **kwargs):
            response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
            raise anthropic.AuthenticationError("rejected", response=response, body=None)

    class FailingClient:
        messages = FailingMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(worksheet.anthropic, "Anthropic", lambda: FailingClient())
    result = read_worksheet(make_png(), LiveWorksheetSource(), topics=["power_rule"])
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "API key missing or invalid"


# ---------------------------------------------------------------------------
# Saved readings and replay
# ---------------------------------------------------------------------------


def test_replay_with_matching_hash_works(tmp_path):
    png = make_png()
    path = tmp_path / "worksheet.json"
    save_worksheet_reading(path, hashlib.sha256(png).hexdigest(), reading_of(item(SOLVER_STATEMENT, "x^{2}")), "fake")
    result = read_worksheet(png, ReplayWorksheetSource(path), topics=["power_rule"])
    assert result["status"] == STATUS_OK
    assert result["source"] == "replay (saved fake reading)"
    assert result["reading"]["items"][0]["statement_latex"] == SOLVER_STATEMENT


def test_replay_with_different_photo_is_an_error(tmp_path):
    path = tmp_path / "worksheet.json"
    save_worksheet_reading(path, hashlib.sha256(make_png(255)).hexdigest(), reading_of(item(SOLVER_STATEMENT, "x")), "live")
    result = read_worksheet(make_png(10), ReplayWorksheetSource(path), topics=["power_rule"])
    assert result["status"] == STATUS_ERROR
    assert result["error"] == "saved reading is for a different photo"
    assert result["reading"] is None


def test_saved_worksheet_file_has_no_image_bytes_or_base64(tmp_path):
    png = make_png()
    path = tmp_path / "worksheet.json"
    save_worksheet_reading(path, hashlib.sha256(png).hexdigest(), reading_of(item(SOLVER_STATEMENT, "x")), "live")
    raw = path.read_bytes()
    assert png not in raw
    assert base64.standard_b64encode(png) not in raw
    saved = load_worksheet_reading(path)
    assert set(saved) >= {"source", "reading", "saved_at", "image_sha256"}
    assert saved["source"] == "live"


def test_save_rejects_unknown_source(tmp_path):
    with pytest.raises(ValueError):
        save_worksheet_reading(tmp_path / "w.json", "a" * 64, reading_of(item(SOLVER_STATEMENT, "x")), "mystery")


def test_load_rejects_a_file_that_is_not_a_worksheet_reading(tmp_path):
    path = tmp_path / "other.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_worksheet_reading(path)
