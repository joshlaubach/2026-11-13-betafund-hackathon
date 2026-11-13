"""The one entry point the chat screens call: request_problems().

Echo-checked problems come from a draft source (live, replay, or fake). A problem
gets the checker label only when drafter.generate() accepted it. Anything served
from the bank gets the bank label, even when its topic is Echo-checked.
Standard library and repo modules only. This module does not load .env; the caller does.
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Optional, Union

from core.bank_fallback import (
    BUILD_DIR,
    LABEL_BANK_FALLBACK,
    LABEL_UNSUPPORTED,
    REPO_ROOT,
    STATUS_UNSUPPORTED,
    echo_checked_topics,
    serve,
)
from core.generated_problems import load_generated
from core.drafter import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    FAKE_DRAFTS,
    LABEL_ACCEPTED,
    LEVELS,
    DraftSource,
    FakeSource,
    LiveSource,
    ReplaySource,
    generate,
)

logger = logging.getLogger(__name__)

MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_FAKE = "fake"
MODE_BANK = "bank"
MODES = (MODE_LIVE, MODE_REPLAY, MODE_FAKE, MODE_BANK)
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_ERROR = "error"
ORIGIN_ECHO = "echo_checked"
ORIGIN_BANK = "bank_fallback"
ORIGIN_REPLAY = "replay_echo_checked"
ECHO_ORIGINS = (ORIGIN_ECHO, ORIGIN_REPLAY)
REPLAY_DEFAULT = REPO_ROOT / "replay" / "power_rule_L2.json"
DRAFTS_PER_REQUEST = 6  # the same batch size scripts/demo_generate.py asks for
ENV_API_KEY = "ANTHROPIC_API_KEY"
ENV_MODEL = "ANTHROPIC_MODEL"
ENV_EFFORT = "ANTHROPIC_EFFORT"


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _argument_error(topic: object, level: object, mode: object, count: object) -> Optional[str]:
    if not isinstance(topic, str) or not topic.strip():
        return "topic must be a non-empty string"
    if not _is_plain_int(level) or level not in LEVELS:
        return f"level must be one of {LEVELS}, got {level!r}"
    if not _is_plain_int(count) or count < 1:
        return f"count must be a positive integer, got {count!r}"
    if mode not in MODES:
        return f"mode must be one of {MODES}, got {mode!r}"
    return None


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _status_for(problems: list[dict], count: int) -> str:
    if not problems:
        return STATUS_UNSUPPORTED
    return STATUS_OK if len(problems) >= count else STATUS_PARTIAL


def _mode_used(mode: str, echo_problems: list[dict], problems: list[dict]) -> Optional[str]:
    if echo_problems:
        return mode
    return MODE_BANK if problems else None


def _result(
    status: str,
    topic: object,
    level: object,
    mode: object,
    mode_used: Optional[str],
    notes: list[str],
    problems: list[dict],
) -> dict:
    counts = {
        "echo_checked": sum(1 for problem in problems if problem["origin"] in ECHO_ORIGINS),
        "bank_fallback": sum(1 for problem in problems if problem["origin"] == ORIGIN_BANK),
    }
    return {
        "status": status,
        "topic": topic,
        "level": level,
        "mode_requested": mode,
        "mode_used": mode_used,
        "notes": list(notes),
        "problems": list(problems),
        "counts": counts,
    }


def _build_source(mode: str, replay_path: Path) -> DraftSource:
    """Raises OSError or ValueError when a replay file cannot be read."""
    if mode == MODE_LIVE:
        return LiveSource(
            os.environ.get(ENV_MODEL, DEFAULT_MODEL),
            os.environ.get(ENV_EFFORT, DEFAULT_EFFORT),
        )
    if mode == MODE_REPLAY:
        return ReplaySource(replay_path)
    return FakeSource(FAKE_DRAFTS)


def _source_notes(mode: str, source: DraftSource, result: dict) -> list[str]:
    if result["status"] != STATUS_OK:
        return [f"{mode} source failed: {result['error']}"]
    notes: list[str] = []
    if isinstance(source, ReplaySource):
        notes.append(
            f"REPLAY of a {source.source.upper()} run (saved {source.saved_at}): the drafts "
            "were saved earlier and re-checked now; no model was called"
        )
    if mode == MODE_FAKE:
        notes.append("fake source: scripted drafts, no model call")
    if not result["accepted"]:
        notes.append(
            f"{mode} source gave {result['drafted']} drafts and the checker accepted none "
            f"({len(result['rejected'])} rejected, {len(result['duplicates'])} duplicates)"
        )
    return notes


def _echo_problem(item: dict, level: int, origin: str) -> dict:
    """Shape a checker-accepted draft. The label is set here, only for accepted drafts."""
    return {
        "statement": item["statement"],
        "answer_latex": item["key_latex"],
        "steps": [],
        "origin": origin,
        "label": LABEL_ACCEPTED,
        "level": level,
        "checker": dict(item["checker"]),
    }


def _draft_problems(
    mode: str, topic: str, level: int, count: int, replay_path: Path, build_dir: Union[str, Path]
) -> tuple[list[dict], list[str]]:
    """Checker-accepted problems from a draft source, plus notes. Never raises for a source failure."""
    if mode == MODE_LIVE and not os.environ.get(ENV_API_KEY, "").strip():
        return [], [f"live source failed: no {ENV_API_KEY} in the environment"]
    try:
        source = _build_source(mode, replay_path)
    except (OSError, ValueError) as error:
        logger.error("could not load saved %s run: %s: %s", mode, type(error).__name__, error)
        return [], [f"{mode} source failed: the saved run could not be loaded"]
    result = generate(
        topic, level, source, count=count, n_drafts=DRAFTS_PER_REQUEST, build_dir=build_dir
    )
    origin = ORIGIN_REPLAY if mode == MODE_REPLAY else ORIGIN_ECHO
    problems = [_echo_problem(item, level, origin) for item in result["accepted"]]
    return problems, _source_notes(mode, source, result)


def _generated_attempt(topic: str, level: int, count: int, seed: Optional[int]) -> list[dict]:
    """Pre-generated problems that passed SymPy offline (core/generated_problems.py). No model call."""
    pool = load_generated(topic, level)
    if not pool:
        return []
    rng = random.Random(seed) if seed is not None else random
    chosen = rng.sample(pool, min(count, len(pool)))
    return [
        {
            "statement": problem["statement"],
            "answer_latex": problem["answer_latex"],
            "steps": [],
            "origin": ORIGIN_ECHO,
            "label": LABEL_ACCEPTED,
            "level": level,
            "checker": {"outcome": "accepted", "method": "sympy_generated_offline"},
        }
        for problem in chosen
    ]


def _echo_attempt(
    mode: str,
    topic: str,
    level: int,
    count: int,
    replay_path: Path,
    build_dir: Union[str, Path],
    seed: Optional[int] = None,
) -> tuple[list[dict], list[str]]:
    """Draft problems only when the mode asks for drafts and the topic is Echo-checked."""
    if mode == MODE_BANK:
        return [], []
    generated = _generated_attempt(topic, level, count, seed)
    if generated:
        return generated, [f"{len(generated)} problem(s) generated offline and verified by SymPy (Echo-checked)"]
    if topic not in echo_checked_topics(build_dir):
        return [], [f"{topic} is not Echo-checked yet; showing bank problems"]
    return _draft_problems(mode, topic, level, count, replay_path, build_dir)


def _bank_problem(problem: dict) -> dict:
    return {
        "statement": problem["statement"],
        "answer_latex": problem["answer_latex"],
        "steps": list(problem["steps"]),
        "origin": ORIGIN_BANK,
        "label": LABEL_BANK_FALLBACK,
        "level": problem["level"],
        "id": problem["id"],
    }


def _bank_fill(
    topic: str,
    level: int,
    needed: int,
    seed: Optional[int],
    build_dir: Union[str, Path],
    taken: set[str],
) -> tuple[list[dict], list[str]]:
    """Up to needed bank problems whose normalized statements are not in taken."""
    if needed < 1:
        return [], []
    served = serve(topic, level, count=needed + len(taken), seed=seed, build_dir=build_dir)
    fresh = [
        problem
        for problem in served["problems"]
        if _normalize(problem["statement"]) not in taken
    ][:needed]
    if not fresh:
        return [], []
    notes = [f"showed {len(fresh)} bank problem(s), labeled bank-verified, not Echo-checked"]
    notes.extend(
        f"bank problem {problem['id']} is level {problem['level']}, not level {level}"
        for problem in fresh
        if problem["level"] != level
    )
    return [_bank_problem(problem) for problem in fresh], notes


def request_problems(
    topic: str,
    level: int,
    mode: str = MODE_LIVE,
    count: int = 3,
    replay_path: Optional[Union[str, Path]] = None,
    build_dir: Union[str, Path] = BUILD_DIR,
    seed: Optional[int] = None,
) -> dict:
    """Up to count practice problems for topic at level. Never raises for bad input or source failures."""
    error = _argument_error(topic, level, mode, count)
    if error is not None:
        return _result(STATUS_ERROR, topic, level, mode, None, [error], [])
    replay = Path(replay_path) if replay_path is not None else REPLAY_DEFAULT
    echo_problems, notes = _echo_attempt(mode, topic, level, count, replay, build_dir, seed)
    taken = {_normalize(problem["statement"]) for problem in echo_problems}
    bank_problems, bank_notes = _bank_fill(
        topic, level, count - len(echo_problems), seed, build_dir, taken
    )
    problems = [*echo_problems, *bank_problems]
    notes = [*notes, *bank_notes]
    if not problems:
        notes.append(LABEL_UNSUPPORTED)
    return _result(
        _status_for(problems, count),
        topic,
        level,
        mode,
        _mode_used(mode, echo_problems, problems),
        notes,
        problems,
    )
