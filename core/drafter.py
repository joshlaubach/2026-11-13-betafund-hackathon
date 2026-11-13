"""Draft practice problems for the Echo-checked topic power_rule.

Three draft sources share one interface: LiveSource (Anthropic API),
ReplaySource (a saved run on disk), and FakeSource (scripted). generate()
asks a source for drafts, builds each statement from the verified fields,
and runs core.derivative_checker.check_derivative on it. Only checker-accepted
drafts are returned as accepted, and only they carry the Echo-checked label.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel

from core.bank_fallback import BUILD_DIR, echo_checked_topics, serve
from core.derivative_checker import ACCEPTED, check_derivative

TOPIC = "power_rule"
DEFAULT_COUNT = 3
DEFAULT_DRAFTS = 5
EXAMPLE_COUNT = 3
EXAMPLE_SEED = 0
LEVELS = (1, 2, 3, 4)
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
MAX_TOKENS = 16000
LABEL_ACCEPTED = "Echo-checked: key verified by the checker"
STATUS_OK = "ok"
STATUS_UNSUPPORTED = "unsupported"
STATUS_ERROR = "error"
SOURCE_LIVE = "live"
SOURCE_FAKE = "fake"
RUN_SOURCES = (SOURCE_LIVE, SOURCE_FAKE)
AUTH_MESSAGE = "API key missing or invalid"
REFUSAL_MESSAGE = "the model declined to write drafts"
EMPTY_MESSAGE = "the model returned no drafts"
UNSUPPORTED_MESSAGE = "only power_rule is supported, and only while its gate is enabled"
OUTPUT_CONFIG_ARG = "output_config"
NO_POINT_TEXT = frozenset({"", "null", "none"})

SYSTEM_PROMPT = (
    "You write calculus practice problems for Echo. Every answer key you write is "
    "machine-checked: SymPy differentiates the function and compares your key with the "
    "result, and a wrong key is rejected. Get every coefficient, power, and sign right. "
    "Return only the structured output requested."
)
GRAMMAR_LINES = (
    r"function_latex: f(x) in LaTeX. Use only digits, x, + and -, ^ for powers (write x^{3}), "
    r"\frac{a}{b}, \sqrt{...}, \sqrt[n]{...}, braces, and parentheses. No other letters, "
    r"variables, or commands.",
    "evaluate_at: null to ask for f'(x), or a plain number such as 2 or -1 to ask for f'(a).",
    "key_latex: the exact answer. With evaluate_at null, the exact f'(x) in LaTeX using x. "
    "With evaluate_at a number, the exact number f'(a). Do not write '+ C'.",
)


class Draft(BaseModel):
    function_latex: str
    evaluate_at: str | None
    key_latex: str


class DraftBatch(BaseModel):
    drafts: list[Draft]


class DraftError(Exception):
    """A draft source could not produce drafts. The message is shown to the user."""


def build_statement(function_latex: str, evaluate_at: str | None) -> str:
    """The statement shown to students, in the same shape as the bank statements."""
    if evaluate_at is None:
        return f"Find $f'(x)$ for $f(x) = {function_latex}$."
    return f"Find $f'({evaluate_at})$ for $f(x) = {function_latex}$. Give an exact answer."


def _point_or_none(evaluate_at: str | None) -> str | None:
    if evaluate_at is None:
        return None
    text = evaluate_at.strip()
    return None if text.lower() in NO_POINT_TEXT else text


def _normalize(text: str) -> str:
    return " ".join(text.split())


class DraftSource:
    """Base for draft sources. source is "live" or "fake"; name is for display."""

    name: str = "source"
    source: str = ""
    last_usage: Optional[dict] = None

    def get_drafts(self, topic: str, level: int, n: int, avoid: list[str]) -> list[Draft]:
        raise NotImplementedError


class FakeSource(DraftSource):
    name = "fake"
    source = SOURCE_FAKE

    def __init__(self, drafts: list[Draft]) -> None:
        self._drafts = list(drafts)

    def get_drafts(self, topic: str, level: int, n: int, avoid: list[str]) -> list[Draft]:
        return self._drafts[:n]


class ReplaySource(DraftSource):
    """Plays back a saved run. The original source ("live" or "fake") is exposed as source."""

    def __init__(self, path: Path | str) -> None:
        run = load_run(path)
        self._run = run
        self.source = run["source"]
        self.saved_at = run.get("saved_at", "unknown time")
        self.name = f"replay (saved {self.source} run)"

    def get_drafts(self, topic: str, level: int, n: int, avoid: list[str]) -> list[Draft]:
        if topic != self._run["topic"] or level != self._run["level"]:
            raise DraftError(
                f"saved run is for {self._run['topic']} level {self._run['level']}, "
                f"not {topic} level {level}"
            )
        return self._run["drafts"][:n]


class LiveSource(DraftSource):
    source = SOURCE_LIVE

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> None:
        self.model = model
        self.effort = effort
        self.name = f"live ({model}, effort {effort})"

    def get_drafts(self, topic: str, level: int, n: int, avoid: list[str]) -> list[Draft]:
        self.last_usage = None
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            raise DraftError(AUTH_MESSAGE)
        examples = serve(topic, level, count=EXAMPLE_COUNT, seed=EXAMPLE_SEED)["problems"]
        prompt = build_prompt(level, n, avoid, examples)
        try:
            batch = self._parse(prompt)
        except anthropic.AuthenticationError as error:
            raise DraftError(AUTH_MESSAGE) from error
        except anthropic.RateLimitError as error:
            raise DraftError("rate limited by the model service; try again later") from error
        except anthropic.APIConnectionError as error:
            raise DraftError("could not reach the model service") from error
        except anthropic.APIStatusError as error:
            raise DraftError(f"the model service returned HTTP {error.status_code}") from error
        return batch.drafts

    def _parse(self, prompt: str) -> DraftBatch:
        client = anthropic.Anthropic()
        request = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": DraftBatch,
        }
        try:
            response = client.messages.parse(**request, output_config={"effort": self.effort})
        except TypeError as error:
            if OUTPUT_CONFIG_ARG not in str(error):
                raise
            response = client.messages.parse(**request)  # retry once without output_config
        self.last_usage = _usage_of(response)
        if response.stop_reason == "refusal":
            raise DraftError(REFUSAL_MESSAGE)
        if response.parsed_output is None:
            raise DraftError(EMPTY_MESSAGE)
        return response.parsed_output


def _usage_of(response: object) -> Optional[dict]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def build_prompt(level: int, count: int, avoid: list[str], examples: list[dict]) -> str:
    example_lines = [
        f"{number}. Problem: {problem['statement']}  Answer: {problem['answer_latex']}"
        for number, problem in enumerate(examples, start=1)
    ]
    avoid_lines = [f"- {text}" for text in avoid] or ["- (none)"]
    lines = [
        f"Write exactly {count} NEW practice problems on the power rule "
        "(differentiating polynomials and rational powers of x) at level "
        f"{level}.",
        "Level 1 is the easiest and level 4 the hardest; match the difficulty of the examples.",
        "Each problem has three fields:",
        *[f"- {line}" for line in GRAMMAR_LINES],
        "Vary the structure; do not repeat a function listed under 'already used'.",
        "",
        "Examples from the verified bank (same topic):",
        *example_lines,
        "",
        "Already used function_latex (do not repeat):",
        *avoid_lines,
    ]
    return "\n".join(lines)


def _new_result(source_name: str) -> dict:
    return {
        "status": STATUS_OK,
        "source": source_name,
        "accepted": [],
        "rejected": [],
        "duplicates": [],
        "drafts": [],
        "drafted": 0,
        "shortfall": 0,
        "tokens": None,
        "error": None,
    }


def _fail(result: dict, status: str, message: str, count: int) -> dict:
    result["status"] = status
    result["error"] = message
    result["shortfall"] = count
    return result


def _is_supported(topic: str, build_dir: Path | str) -> bool:
    return topic == TOPIC and topic in echo_checked_topics(build_dir)


def _check_one(draft: Draft) -> tuple[str, Optional[str], dict]:
    function = draft.function_latex.strip()
    key = draft.key_latex.strip()
    at = _point_or_none(draft.evaluate_at)
    return function, at, check_derivative(function, key, at)


def _accepted_entry(function: str, key: str, at: Optional[str], verdict: dict) -> dict:
    return {
        "statement": build_statement(function, at),
        "function_latex": function,
        "key_latex": key,
        "evaluate_at": at,
        "label": LABEL_ACCEPTED,
        "checker": {
            "outcome": verdict["outcome"],
            "reason": verdict["reason"],
            "true_answer": verdict["true_answer"],
            "samples": list(verdict["samples"]),
        },
    }


def _rejected_entry(function: str, key: str, at: Optional[str], verdict: dict) -> dict:
    return {
        "statement": build_statement(function, at),
        "key_latex": key,
        "outcome": verdict["outcome"],
        "reason": verdict["reason"],
    }


def _check_drafts(drafts: list[Draft], avoid: list[str], count: int, result: dict) -> None:
    seen = {_normalize(text) for text in avoid}
    accepted: list[dict] = []
    rejected: list[dict] = []
    for draft in drafts:
        function_key = _normalize(draft.function_latex)
        if function_key in seen:
            result["duplicates"].append(draft.function_latex.strip())
            continue
        seen.add(function_key)
        function, at, verdict = _check_one(draft)
        key = draft.key_latex.strip()
        if verdict["outcome"] == ACCEPTED:
            accepted.append(_accepted_entry(function, key, at, verdict))
        else:
            rejected.append(_rejected_entry(function, key, at, verdict))
    result["accepted"] = accepted[:count]
    result["rejected"] = rejected


def generate(
    topic: str,
    level: int,
    source: DraftSource,
    count: int = DEFAULT_COUNT,
    n_drafts: int = DEFAULT_DRAFTS,
    avoid: Optional[list[str]] = None,
    build_dir: Path | str = BUILD_DIR,
) -> dict:
    """Ask source for drafts and keep the checker-accepted ones. Never raises for a source failure."""
    avoid_list = list(avoid or [])
    result = _new_result(source.name)
    if not _is_supported(topic, build_dir):
        return _fail(result, STATUS_UNSUPPORTED, UNSUPPORTED_MESSAGE, count)
    if level not in LEVELS:
        return _fail(result, STATUS_ERROR, f"level must be one of {LEVELS}, got {level!r}", count)
    try:
        drafts = list(source.get_drafts(topic, level, n_drafts, avoid_list))[:n_drafts]
    except Exception as error:  # a draft-source failure must not crash the caller
        return _fail(result, STATUS_ERROR, str(error) or type(error).__name__, count)
    result["tokens"] = dict(source.last_usage) if source.last_usage else None
    result["drafted"] = len(drafts)
    result["drafts"] = [draft.model_dump() for draft in drafts]
    _check_drafts(drafts, avoid_list, count, result)
    result["shortfall"] = max(count - len(result["accepted"]), 0)
    return result


def save_run(path: Path | str, topic: str, level: int, drafts: list[Draft], source: str) -> None:
    """Write a run to a JSON file. source is "live" or "fake"."""
    if source not in RUN_SOURCES:
        raise ValueError(f"source must be one of {RUN_SOURCES}, got {source!r}")
    payload = {
        "topic": topic,
        "level": level,
        "source": source,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "drafts": [draft.model_dump() for draft in drafts],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_run(path: Path | str) -> dict:
    """Read a saved run. Raises ValueError when the file is not a valid run."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("source") not in RUN_SOURCES:
        raise ValueError(f"{path} is not a saved Echo draft run")
    if not isinstance(data.get("drafts"), list) or not isinstance(data.get("level"), int):
        raise ValueError(f"{path} is missing its level or drafts")
    drafts = [Draft.model_validate(item) for item in data["drafts"]]
    return {**data, "drafts": drafts}
