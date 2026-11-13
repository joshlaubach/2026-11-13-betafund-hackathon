"""Offline generator: write Echo-checked derivative problems to docs/echo_checked_problems.json.

Per problem: the model writes the answer g(x) first, then a function f(x) whose
derivative is g(x), and SymPy verifies the pair (core.generated_problems.verify_pair).
Only verified problems are kept. Run by hand, never by the app:
  python scripts/generate_echo_problems.py --per-level 10
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import anthropic  # noqa: E402

from core.drafter import LABEL_ACCEPTED  # noqa: E402
from core.generated_problems import (  # noqa: E402
    GENERATED_PATH,
    GENERATED_TOPICS,
    NET_CHANGE_TOPIC,
    VERSION,
    verify_integral,
    verify_pair,
)

logger = logging.getLogger(__name__)

LEVELS = (1, 2, 3, 4)
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 512
DEFAULT_PER_LEVEL = 10
DEFAULT_WORKERS = 6
DEFAULT_ATTEMPTS = 12
TOPIC_TEXT = {
    "chain_rule": "the chain rule: a composition such as a power, root, or fraction of an inner polynomial",
    "quotient_rule": "the quotient rule: a quotient of polynomials, possibly with a root",
}
LEVEL_TEXT = {
    1: "one simple composition or quotient",
    2: "a composition or quotient with a larger inner polynomial",
    3: "a composition or quotient with a root or a second layer",
    4: "a nested or multi-step one",
}
SYSTEM = (
    "You write calculus practice problems for Echo. Each answer is machine-checked by SymPy: "
    "it differentiates your function and compares the result with your answer. Be exact. "
    "Return only the structured output requested."
)
SYNTAX_RULE = (
    "Write it in plain SymPy syntax in x: use * for multiplication, ** for powers, sqrt(...) "
    "for roots, / for division, and parentheses. Use only x, digits, + - * / ( ) ** and sqrt. "
    "No '+ C', no other variables, no words."
)
INTEGRAL_LEVEL_TEXT = {
    1: "a simple polynomial plus one exponential or a root",
    2: "a polynomial with a larger term, or an exponential times a polynomial",
    3: "a root or an exponential of a polynomial, with a second term",
    4: "a nested or multi-term function",
}
INTEGRAL_SYNTAX_RULE = (
    "Write it in plain SymPy syntax in t: use * for multiplication, ** for powers, sqrt(...) "
    "for roots, exp(...) for e to a power, / for division, and parentheses. Use only t, digits, "
    "+ - * / ( ) ** sqrt and exp. No '+ C', no other variables, no words."
)


class AnswerDraft(BaseModel):
    answer: str


class FunctionDraft(BaseModel):
    function: str


class AntiderivativeDraft(BaseModel):
    antiderivative: str


class VelocityDraft(BaseModel):
    velocity: str
    a: int
    b: int


def make_live_call(model: str):
    """Return call(prompt, schema) that asks the Anthropic API for structured output."""
    client = anthropic.Anthropic()

    def call(prompt: str, schema):
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        return response.parsed_output

    return call


def _answer_prompt(topic: str, level: int, taken: list[str]) -> str:
    used = "\n".join(f"- {text}" for text in taken) or "- (none)"
    return "\n".join(
        [
            f"Topic: {TOPIC_TEXT[topic]}.",
            f"Level {level} of 4: {LEVEL_TEXT[level]}.",
            "Write ONE exact derivative g(x), the answer to a practice problem on this topic. "
            + SYNTAX_RULE,
            "Do not repeat any of these already used:",
            used,
        ]
    )


def _function_prompt(answer: str) -> str:
    return "\n".join(
        [
            f"Here is a derivative g(x) = {answer}.",
            "Write a function f(x) whose exact derivative is g(x), so that d/dx f(x) equals g(x) exactly. "
            + SYNTAX_RULE,
        ]
    )


def _antiderivative_prompt(level: int, taken: list[str]) -> str:
    used = "\n".join(f"- {text}" for text in taken) or "- (none)"
    return "\n".join(
        [
            "Topic: net change and total distance. Each problem integrates a velocity v(t) "
            "over a time interval, and its answer is checked by SymPy.",
            f"Level {level} of 4: {INTEGRAL_LEVEL_TEXT[level]}.",
            "Write ONE antiderivative F(t), a nontrivial function of t. " + INTEGRAL_SYNTAX_RULE,
            "Do not repeat any of these already used:",
            used,
        ]
    )


def _velocity_prompt(antiderivative: str) -> str:
    return "\n".join(
        [
            f"Here is an antiderivative F(t) = {antiderivative}.",
            "Write velocity = diff(F, t), the exact derivative of F in t, and integer bounds a and b "
            "with 0 <= a < b <= 5, such that velocity >= 0 for every t from a to b. " + INTEGRAL_SYNTAX_RULE,
        ]
    )


def _normalize(text: str) -> str:
    return " ".join(text.split())


def generate_one(
    topic: str,
    level: int,
    call,
    attempts: int,
    taken: set[str],
    lock: threading.Lock | None = None,
) -> dict | None:
    """Try up to attempts times to produce one verified problem not already in taken."""
    guard = lock or threading.Lock()
    for attempt in range(1, attempts + 1):
        with guard:
            snapshot = sorted(taken)
        try:
            answer = call(_answer_prompt(topic, level, snapshot), AnswerDraft).answer
            function = call(_function_prompt(answer), FunctionDraft).function
        except Exception as error:  # a failed call is a failed attempt, never a crash
            logger.warning(
                "attempt %d for %s level %d failed: %s", attempt, topic, level, type(error).__name__
            )
            continue
        verdict = verify_pair(function, answer)
        if not verdict["ok"]:
            continue
        statement = _normalize(verdict["statement"])
        with guard:
            if statement in taken or verdict["answer_latex"] in taken:
                continue
            taken.add(statement)
            taken.add(verdict["answer_latex"])
        return {
            "topic": topic,
            "level": level,
            "statement": verdict["statement"],
            "answer_latex": verdict["answer_latex"],
            "function_latex": verdict["function_latex"],
            "sympy_check": "passed",
            "label": LABEL_ACCEPTED,
        }
    return None


def generate_one_integral(
    level: int,
    call,
    attempts: int,
    taken: set[str],
    lock: threading.Lock | None = None,
) -> dict | None:
    """Try up to attempts times to produce one verified net-change problem not already in taken."""
    guard = lock or threading.Lock()
    for attempt in range(1, attempts + 1):
        with guard:
            snapshot = sorted(taken)
        try:
            first = call(_antiderivative_prompt(level, snapshot), AntiderivativeDraft)
            antiderivative = first.antiderivative if first is not None else None
            draft = call(_velocity_prompt(antiderivative), VelocityDraft) if antiderivative else None
        except Exception as error:  # a failed call is a failed attempt, never a crash
            logger.warning(
                "attempt %d for %s level %d failed: %s",
                attempt, NET_CHANGE_TOPIC, level, type(error).__name__,
            )
            continue
        if draft is None:  # the model returned no structured output: a failed attempt
            logger.warning("attempt %d for %s level %d returned no output", attempt, NET_CHANGE_TOPIC, level)
            continue
        verdict = verify_integral(antiderivative, draft.velocity, draft.a, draft.b)
        if not verdict["ok"]:
            continue
        statement = _normalize(verdict["statement"])
        with guard:
            if statement in taken or verdict["answer_latex"] in taken:
                continue
            taken.add(statement)
            taken.add(verdict["answer_latex"])
        return {
            "topic": NET_CHANGE_TOPIC,
            "level": level,
            "statement": verdict["statement"],
            "answer_latex": verdict["answer_latex"],
            "velocity_latex": verdict["velocity_latex"],
            "antiderivative": antiderivative,
            "velocity_text": draft.velocity,
            "a": draft.a,
            "b": draft.b,
            "sympy_check": "passed",
            "label": LABEL_ACCEPTED,
        }
    return None


def _run_slot(topic, level, call_factory, attempts, taken, lock):
    try:
        call = call_factory()
    except Exception as error:
        logger.warning("could not start a model client: %s", type(error).__name__)
        return None
    if topic == NET_CHANGE_TOPIC:
        return generate_one_integral(level, call, attempts, taken, lock)
    return generate_one(topic, level, call, attempts, taken, lock)


def _kept_entries(path: Path, run_topics: set[str]) -> list[dict]:
    """Saved entries for topics NOT run this time. A missing or unreadable file keeps nothing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("could not read existing problems in %s (%s); starting empty", path, type(error).__name__)
        return []
    problems = data.get("problems") if isinstance(data, dict) else None
    if not isinstance(problems, list):
        logger.warning("existing file %s has the wrong shape; starting empty", path)
        return []
    return [item for item in problems if isinstance(item, dict) and item.get("topic") not in run_topics]


def run(
    topics,
    per_level: int,
    workers: int,
    attempts: int,
    call_factory,
    out: Path | str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Generate per_level slots for each topic and level 1 to 4, then write the JSON file."""
    started = time.monotonic()
    count_lock = threading.Lock()
    total_calls = [0]

    def counted_factory():
        inner = call_factory()

        def counted(prompt, schema):
            with count_lock:
                total_calls[0] += 1
            return inner(prompt, schema)

        return counted

    keys = [(topic, level) for topic in sorted(topics) for level in LEVELS]
    taken = {key: set() for key in keys}
    locks = {key: threading.Lock() for key in keys}
    results: dict[tuple[str, int], list] = {key: [None] * per_level for key in keys}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for key in keys:
            for slot in range(per_level):
                futures[pool.submit(
                    _run_slot, key[0], key[1], counted_factory, attempts, taken[key], locks[key]
                )] = (key, slot)
        for future, (key, slot) in futures.items():
            results[key][slot] = future.result()

    new_problems = []
    for key in keys:
        accepted = [item for item in results[key] if item is not None]
        for number, item in enumerate(accepted, start=1):
            topic, level = key
            new_problems.append({"id": f"gen-{topic}-L{level}-{number}", **item})
    # Keep saved entries for topics not run this time; the run topics are replaced by new_problems.
    target = Path(out)
    problems = _kept_entries(target, set(topics)) + new_problems
    problems.sort(key=lambda p: (str(p.get("topic")), str(p.get("level")), str(p.get("id"))))
    elapsed = time.monotonic() - started
    payload = {
        "version": VERSION,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "problems": problems,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    accepted_total = len(new_problems)
    return {
        "accepted": {f"{topic} L{level}": sum(1 for p in new_problems if p["topic"] == topic and p["level"] == level)
                     for topic, level in keys},
        "accepted_total": accepted_total,
        "total_calls": total_calls[0],
        "total_seconds": round(elapsed, 1),
        "seconds_per_accepted": round(elapsed / accepted_total, 2) if accepted_total else None,
        "out": str(target),
    }


def parse_args(default_model: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-level", type=int, default=DEFAULT_PER_LEVEL)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS, help="max tries per problem slot")
    parser.add_argument("--topics", nargs="+", default=list(GENERATED_TOPICS), choices=GENERATED_TOPICS)
    parser.add_argument("--out", type=Path, default=GENERATED_PATH)
    parser.add_argument("--model", default=default_model)
    return parser.parse_args()


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))
    summary = run(
        args.topics,
        args.per_level,
        args.workers,
        args.attempts,
        lambda: make_live_call(args.model),
        args.out,
        model=args.model,
    )
    for key, count in summary["accepted"].items():
        print(f"{key}: accepted {count}")
    print(f"accepted total: {summary['accepted_total']}")
    print(f"calls: {summary['total_calls']}")
    print(f"seconds: {summary['total_seconds']}")
    print(f"seconds per accepted: {summary['seconds_per_accepted']}")
    print(f"wrote: {summary['out']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
