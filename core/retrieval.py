"""Lexical retrieval over Echo's eligible verified bank problems (BM25, standard library only).

search() ranks eligible bank problems against a student's words. Filters (topic, course, level) and
exclusions apply before ranking. The index is built once from docs/verified_problems.json and cached.
No embeddings and no vector store: the corpus is a few thousand short documents, so lexical ranking
is enough. Only problems that scripts/audit_bank.py marks eligible are indexed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from core.bank_fallback import BANK_PATH
from scripts.audit_bank import AUDITED_LEVELS, classify, load_bank, parse_level

BM25_K1 = 1.5
BM25_B = 0.75
DEFAULT_K = 3
MIN_TOKEN_CHARS = 2
MIN_SCORE = 0.0
TOKEN_PATTERN = re.compile(r"[a-z]+")
LATEX_COMMAND_PATTERN = re.compile(r"\\([A-Za-z]+)")
LATEX_NOISE_PATTERN = re.compile(r"[\\${}]")
DROPPED_COMMANDS = frozenset(
    {
        "left", "right", "displaystyle", "textstyle", "mathrm", "mathbf", "text",
        "quad", "qquad", "big", "Big", "bigl", "bigr",
    }
)
COMMAND_WORDS = {"int": "integral", "infty": "infinity", "cdot": "times"}
# Phrases a student says that map to a word the bank uses. Applied to documents and queries alike.
PHRASE_EXPANSIONS = (
    ("chain rule", "composite"),
    ("mean value", "mvt"),
    ("intermediate value", "ivt"),
    ("related rate", "rate change"),
    ("e to the", "exponential"),
)
# Word forms that mean the same thing in these calculus texts. Applied to documents and queries alike.
CANONICAL_WORDS = {
    "differentiate": "derivative",
    "differentiation": "derivative",
    "derivatives": "derivative",
    "antiderivative": "integral",
    "antiderivatives": "integral",
    "integrate": "integral",
    "integration": "integral",
    "integrals": "integral",
    "lim": "limit",
    "limits": "limit",
    "algebraic": "algebra",
    "sub": "substitution",
    "usub": "substitution",
    "logarithm": "log",
    "logarithmic": "log",
    "logarithms": "log",
    "ln": "log",
    "trigonometric": "trig",
    "trigonometry": "trig",
    "sine": "sin",
    "cosine": "cos",
    "arctangent": "arctan",
    "arcsine": "arcsin",
    "sandwich": "squeeze",
    "newtons": "newton",
    "lhopital": "hopital",
    "asymptotes": "asymptote",
    "maximum": "extremum",
    "minimum": "extremum",
    "extrema": "extremum",
    "extreme": "extremum",
    "max": "extremum",
    "min": "extremum",
    "maximize": "optimization",
    "minimize": "optimization",
    "optimize": "optimization",
    "converge": "convergence",
    "converges": "convergence",
    "diverge": "convergence",
    "diverges": "convergence",
    "divergence": "convergence",
    "tangents": "tangent",
    "slopes": "slope",
    "areas": "area",
    "volumes": "volume",
    "rates": "rate",
    "fraction": "frac",
    "fractions": "frac",
}
STOPWORDS = frozenset(
    {
        "a", "about", "an", "and", "are", "as", "at", "be", "been", "by", "can", "could", "do",
        "does", "dont", "for", "from", "get", "give", "had", "has", "have", "how", "i", "if", "im",
        "in", "into", "is", "it", "its", "just", "let", "make", "me", "my", "not", "of", "on", "or",
        "our", "please", "should", "so", "some", "step", "steps", "than", "that", "the", "their",
        "them", "then", "there", "these", "this", "those", "to", "too", "us", "use", "using", "was",
        "we", "were", "what", "when", "where", "which", "who", "why", "will", "with", "would", "you",
        "your", "want", "need", "help", "find", "evaluate", "compute", "problem", "question", "show",
        "explain", "exact", "answer", "solve",
    }
)


@dataclass(frozen=True)
class BankDocument:
    """One eligible bank problem, with its term counts for BM25."""

    topic: str
    topic_title: str
    course: str
    problem_id: str
    level: int
    statement: str
    steps: tuple[str, ...]
    answer_latex: str
    term_counts: Mapping[str, int]
    length: int


@dataclass(frozen=True)
class Index:
    """All eligible documents with their global inverse document frequencies."""

    documents: tuple[BankDocument, ...]
    idf: Mapping[str, float]
    average_length: float


def normalize_latex(text: str) -> str:
    """LaTeX turned into plain words: commands become words, ^ becomes 'power', braces and dollars go."""

    def command_word(match: re.Match) -> str:
        name = match.group(1)
        if name in DROPPED_COMMANDS:
            return " "
        return " " + COMMAND_WORDS.get(name, name) + " "

    text = LATEX_COMMAND_PATTERN.sub(command_word, text)
    text = text.replace("^", " power ").replace("_", " ")
    return LATEX_NOISE_PATTERN.sub(" ", text)


def _expand_phrases(text: str) -> str:
    expanded = text
    for phrase, extra in PHRASE_EXPANSIONS:
        if phrase in text:
            expanded = f"{expanded} {extra}"
    return expanded


def tokenize(text: str) -> list[str]:
    """Lowercase words of a text after LaTeX normalization, with synonyms merged and stopwords removed."""
    lowered = _expand_phrases(normalize_latex(text).lower())
    tokens: list[str] = []
    for word in TOKEN_PATTERN.findall(lowered):
        canonical = CANONICAL_WORDS.get(word, word)
        if len(canonical) < MIN_TOKEN_CHARS or canonical in STOPWORDS:
            continue
        tokens.append(canonical)
    return tokens


def _document(problem: dict) -> BankDocument:
    steps = tuple(str(step) for step in (problem.get("steps") or []))
    answer = problem.get("answer") or {}
    title = str(problem.get("topic_title", ""))
    text = "\n".join([title, str(problem["statement"]), *steps])
    counts = Counter(tokenize(text))
    return BankDocument(
        topic=str(problem["topic"]),
        topic_title=title,
        course=str(problem.get("course", "")),
        problem_id=str(problem["id"]),
        level=parse_level(problem),
        statement=str(problem["statement"]),
        steps=steps,
        answer_latex=str(answer.get("latex", "")),
        term_counts=dict(counts),
        length=sum(counts.values()),
    )


def build_index(problems: Iterable[dict]) -> Index:
    """Index the eligible problems, one per (topic, id), in a fixed order."""
    ordered = sorted(problems, key=lambda problem: (str(problem["topic"]), str(problem["id"])))
    documents: list[BankDocument] = []
    seen: set[tuple[str, str]] = set()
    for problem in ordered:
        if classify(problem) is not None:
            continue
        key = (str(problem["topic"]), str(problem["id"]))
        if key in seen:
            continue
        seen.add(key)
        documents.append(_document(problem))
    document_frequency: Counter = Counter()
    for document in documents:
        document_frequency.update(document.term_counts.keys())
    count = len(documents)
    idf = {
        term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
        for term, frequency in document_frequency.items()
    }
    total_length = sum(document.length for document in documents)
    average = total_length / count if count and total_length else 1.0
    return Index(tuple(documents), idf, average)


@lru_cache(maxsize=1)
def _load_index() -> Index:
    """The index over the current bank file. Built once per process."""
    return build_index(load_bank(BANK_PATH))


def eligible_topic_ids() -> frozenset[str]:
    """Topic ids that have at least one eligible bank problem."""
    return frozenset(document.topic for document in _load_index().documents)


def _score(document: BankDocument, query_terms: frozenset[str], index: Index) -> float:
    norm = BM25_K1 * (1 - BM25_B + BM25_B * document.length / index.average_length)
    total = 0.0
    for term in query_terms:
        frequency = document.term_counts.get(term, 0)
        if frequency:
            total += index.idf[term] * frequency * (BM25_K1 + 1) / (frequency + norm)
    return total


def _exclusions(exclude_ids: Iterable[object]) -> frozenset[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for item in exclude_ids:
        if not (
            isinstance(item, tuple) and len(item) == 2 and all(isinstance(part, str) for part in item)
        ):
            raise ValueError("exclude_ids must be (topic, problem_id) pairs of strings")
        keys.add((item[0], item[1]))
    return frozenset(keys)


def _matches(
    document: BankDocument,
    topic: Optional[str],
    course: Optional[str],
    level: Optional[int],
    excluded: frozenset[tuple[str, str]],
) -> bool:
    if topic is not None and document.topic != topic:
        return False
    if course is not None and document.course != course:
        return False
    if level is not None and document.level != level:
        return False
    return (document.topic, document.problem_id) not in excluded


def _candidate_pool(
    index: Index,
    topic: Optional[str],
    course: Optional[str],
    level: Optional[int],
    excluded: frozenset[tuple[str, str]],
) -> list[BankDocument]:
    """Documents that pass the filters. A topic that matches nothing relaxes to the course, then everything."""
    relaxations = [(topic, course, level)]
    if topic is not None:
        relaxations += [(None, course, level), (None, None, None)]
    for stage_topic, stage_course, stage_level in relaxations:
        pool = [
            document
            for document in index.documents
            if _matches(document, stage_topic, stage_course, stage_level, excluded)
        ]
        if pool:
            return pool
    return []


def _result(document: BankDocument, score: float) -> dict:
    return {
        "topic": document.topic,
        "topic_title": document.topic_title,
        "problem_id": document.problem_id,
        "level": document.level,
        "statement": document.statement,
        "steps": list(document.steps),
        "answer_latex": document.answer_latex,
        "score": round(score, 6),
    }


def _check_arguments(query: object, level: object, k: object) -> None:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    if level is not None and (isinstance(level, bool) or level not in AUDITED_LEVELS):
        raise ValueError(f"level must be one of {AUDITED_LEVELS} or None, got {level!r}")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be a positive integer, got {k!r}")


def search(
    query: str,
    topic: Optional[str] = None,
    course: Optional[str] = None,
    level: Optional[int] = None,
    exclude_ids: Iterable[tuple[str, str]] = (),
    k: int = DEFAULT_K,
) -> list[dict]:
    """Up to k eligible bank problems ranked by BM25 for query.

    Filters apply before ranking. A topic filter that matches nothing falls back to the course,
    then to every problem. Results with no matching term are never returned. Order is score
    descending, then problem id, then topic, so the same call always gives the same list.
    """
    _check_arguments(query, level, k)
    excluded = _exclusions(exclude_ids)
    terms = frozenset(tokenize(query))
    if not terms:
        return []
    index = _load_index()
    scored: list[tuple[float, BankDocument]] = []
    for document in _candidate_pool(index, topic, course, level, excluded):
        score = _score(document, terms, index)
        if score > MIN_SCORE:
            scored.append((score, document))
    scored.sort(key=lambda pair: (-pair[0], pair[1].problem_id, pair[1].topic))
    return [_result(document, score) for score, document in scored[:k]]
