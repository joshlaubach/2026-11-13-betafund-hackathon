"""Shapes of worksheet text: function definitions in a part's shared setup, and the asks in a part.

Everything here reads by shape only. A definition's body must pass core.latex_reader with the
definition's own variable; a body that cannot be read is dropped, so its part falls to the AI ladder
instead of being guessed. A definition followed by a domain restriction ("for x>0") is RESTRICTED:
parse_definitions leaves it out, so any part that uses it falls to the AI ladder too. Nothing here
calls SymPy.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from core.input_boundary import BoundaryError
from core.latex_reader import read_latex

ASK_VERBS = r"(?:Find|Compute|Determine|Calculate|Evaluate)"
EULER_NUMBER = "e"  # never a variable: e^{-t} is exp(-t)
_TEXT_WRAPPER = re.compile(r"\\(?:text|mathrm|textbf)\{([^{}]*)\}")
_ASK_PREFIX = re.compile(r"^" + ASK_VERBS + r"\s+")
# A genuine writing instruction: write/explain/justify/interpret, or state/give a sentence, words, reasoning, or why.
_WRITING_VERB = r"(?:write|explain|justify|interpret)\b"
_SENTENCE_ASK = r"(?:state|give)\s+(?:(?:your|a|an|one|in|complete)\s+)*(?:sentence|words|reasoning|why)\b"
_WRITING_CLAUSE = re.compile(
    r"[,.;]?\s*(?:and\s+)?(?:" + _WRITING_VERB + "|" + _SENTENCE_ASK + r").*$", re.IGNORECASE
)
# Anything in a removed clause that asks for mathematics: such a clause is never stripped.
_MATH_REQUEST = re.compile(
    r"[<>=\u2264\u2265\u2260]|\\(?:le|leq|ge|geq|ne|neq|frac|int|lim|sqrt)\b|\d|[A-Za-z]'"
    r"|(?<![A-Za-z])[A-Za-z]'*\(\s*[A-Za-z0-9]|\b(?:where|for which|on what interval|on which)\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"\.\s+")
_BODY_BREAK = re.compile(r"\s+(?=(?:[A-Za-z]{3,}|if|on)\b)")
_RESTRICTION_WORD = re.compile(r"\b(?:defined\s+)?(?:for|when|where|on|if|with)\b(?P<rest>.*)", re.IGNORECASE)
_RESTRICTION_MARK = re.compile(
    r"<|>|[\u2264\u2265\u2260]|\\(?:le|leq|ge|geq|ne|neq|in|infty)(?![A-Za-z])"
    r"|\[[^\]]*,[^\]]*\]|\([^)]*,[^)]*\)"
)
_BODY_END = r"(?=\.\s|\.$|;|$)"
_DEFINITION = re.compile(r"([A-Za-z])\s*\(\s*([A-Za-z])\s*\)\s*=\s*(.+?)" + _BODY_END)
_Y_DEFINITION = re.compile(r"(?<![A-Za-z(])y\s*=\s*(.+?)" + _BODY_END)
_SINGLE_LETTER = re.compile(r"(?<![A-Za-z\\])([A-Za-z])(?![A-Za-z])")
_CALLED = re.compile(r"(?<![A-Za-z0-9\\])([A-Za-z])'*\s*\(")


class Definition(NamedTuple):
    """A function such as v(t) = 1 - e^{-t}: its name, the variable it is written in, and its body.

    restricted is True when the setup restricts the domain after the body ("for x>0").
    """

    name: str
    variable: str
    body_latex: str
    restricted: bool = False


def plain_text(statement: str) -> str:
    """Drop $ signs, \\displaystyle and \\text{...} wrappers, and collapse whitespace.

    The reading model sometimes wraps the words of a statement in \\text{...} and sometimes
    delimits the math with $; both must reach the same plain shape.
    """
    unwrapped = _TEXT_WRAPPER.sub(r" \1 ", statement.replace("$", " ").replace("\\displaystyle", " "))
    return " ".join(unwrapped.split())


def _readable(definition: Definition) -> bool:
    try:
        read_latex(definition.body_latex, (definition.variable,))
    except BoundaryError:
        return False
    return True


def _only_variable(body: str) -> str | None:
    """The single letter a body is written in, or None when there is not exactly one."""
    names = set(_SINGLE_LETTER.findall(body)) - {EULER_NUMBER}
    return names.pop() if len(names) == 1 else None


def _trim_prose(body: str) -> str:
    """Cut a definition body at the first plain word, so "1 - e^{-t} meters per second" keeps "1 - e^{-t}".

    LaTeX commands start with a backslash, so a word after a space is prose, not math.
    """
    return _BODY_BREAK.split(body.strip(), maxsplit=1)[0].strip()


def _restricted_clause(remainder: str) -> bool:
    """True when prose after a body opens a clause such as "for x>0" or "on [0, 1]"."""
    match = _RESTRICTION_WORD.search(remainder)
    return match is not None and _RESTRICTION_MARK.search(match.group("rest")) is not None


def _split_body(raw: str) -> tuple[str, bool]:
    """The body without its trailing prose, and whether that prose restricts the domain."""
    body = raw.strip()
    trimmed = _trim_prose(body)
    return trimmed, _restricted_clause(body[len(trimmed):])


def _definitions_in(text: str) -> list[Definition]:
    explicit = []
    for name, variable, raw in _DEFINITION.findall(text):
        body, restricted = _split_body(raw)
        explicit.append(Definition(name, variable, body, restricted))
    implicit = []
    for raw in _Y_DEFINITION.findall(text):
        body, restricted = _split_body(raw)
        variable = _only_variable(body)
        if variable is not None:
            implicit.append(Definition("y", variable, body, restricted))
    return [definition for definition in explicit + implicit if _readable(definition)]


def _grouped(context: str) -> dict[str, list[Definition]]:
    found: dict[str, list[Definition]] = {}
    for definition in _definitions_in(plain_text(context)):
        found.setdefault(definition.name, []).append(definition)
    return found


def parse_definitions(context: str) -> dict[str, Definition]:
    """Unrestricted definitions in the shared setup, by name.

    A name defined two different ways is left out, and so is a name whose definition is restricted
    to a domain: SymPy would otherwise ignore the restriction.
    """
    return {
        name: entries[0]
        for name, entries in _grouped(context).items()
        if not any(entry.restricted for entry in entries)
        and len({(entry.variable, entry.body_latex) for entry in entries}) == 1
    }


def restricted_names(context: str) -> frozenset[str]:
    """Names the shared setup defines with a domain restriction. parse_definitions leaves these out."""
    return frozenset(name for name, entries in _grouped(context).items() if any(e.restricted for e in entries))


def _without_writing(text: str) -> str:
    """The text without a trailing writing instruction, unless the removed clause also asks for math."""
    match = _WRITING_CLAUSE.search(text)
    if match is None or _MATH_REQUEST.search(match.group(0)):
        return text
    return text[: match.start()]


def split_asks(statement: str) -> tuple[str, ...]:
    """The asks in a part, in order, without writing instructions ("and write a sentence") or final periods."""
    trimmed = _without_writing(plain_text(statement))
    pieces = (piece.strip().rstrip(".").strip() for piece in _SENTENCE_BREAK.split(trimmed))
    return tuple(piece for piece in pieces if piece)


def without_writing_ask(statement: str) -> str:
    """The statement without "write a sentence..." instructions, which are graded separately and never shown to a model.

    A model that is asked for a sentence it cannot see would call correct math incomplete.
    """
    trimmed = _without_writing(statement).strip()
    return trimmed or statement


def ask_label(ask: str) -> str:
    """The ask without its verb: "Compute v'(0)" gives "v'(0)"."""
    return _ASK_PREFIX.sub("", ask, count=1)


def missing_definitions(statement: str, context: str) -> tuple[str, ...]:
    """Function names the statement uses that neither the shared setup nor the statement defines.

    A name the setup defines with a domain restriction is not missing; it is defined, and its part goes to the AI ladder.
    """
    joined = " ".join(part for part in (context, statement) if part)
    defined = parse_definitions(joined)
    restricted = restricted_names(joined)
    called = dict.fromkeys(_CALLED.findall(plain_text(statement)))
    return tuple(name for name in called if name not in defined and name not in restricted)
