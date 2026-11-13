"""Shapes of worksheet text: function definitions in a part's shared setup, and the asks in a part.

Everything here reads by shape only. A definition's body must pass core.latex_reader with the
definition's own variable; a body that cannot be read is dropped, so its part falls to the AI ladder
instead of being guessed. Nothing here calls SymPy.
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
_WRITING_CLAUSE = re.compile(
    r"[,.;]?\s*(?:and\s+)?(?:write|explain|state|justify|interpret)\b.*$", re.IGNORECASE
)
_SENTENCE_BREAK = re.compile(r"\.\s+")
_PROSE_START = re.compile(r"\s+(?=[A-Za-z]{3,}\b)")
_BODY_END = r"(?=\.\s|\.$|;|$)"
_DEFINITION = re.compile(r"([A-Za-z])\s*\(\s*([A-Za-z])\s*\)\s*=\s*(.+?)" + _BODY_END)
_Y_DEFINITION = re.compile(r"(?<![A-Za-z(])y\s*=\s*(.+?)" + _BODY_END)
_SINGLE_LETTER = re.compile(r"(?<![A-Za-z\\])([A-Za-z])(?![A-Za-z])")
_CALLED = re.compile(r"(?<![A-Za-z0-9\\])([A-Za-z])'*\s*\(")


class Definition(NamedTuple):
    """A function such as v(t) = 1 - e^{-t}: its name, the variable it is written in, and its body."""

    name: str
    variable: str
    body_latex: str


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
    return _PROSE_START.split(body.strip(), maxsplit=1)[0].strip()


def _definitions_in(text: str) -> list[Definition]:
    explicit = [
        Definition(name, variable, _trim_prose(body))
        for name, variable, body in _DEFINITION.findall(text)
    ]
    implicit = []
    for body in _Y_DEFINITION.findall(text):
        trimmed = _trim_prose(body)
        variable = _only_variable(trimmed)
        if variable is not None:
            implicit.append(Definition("y", variable, trimmed))
    return [definition for definition in explicit + implicit if _readable(definition)]


def parse_definitions(context: str) -> dict[str, Definition]:
    """Definitions in the shared setup, by name. A name defined two different ways is left out."""
    found: dict[str, list[Definition]] = {}
    for definition in _definitions_in(plain_text(context)):
        found.setdefault(definition.name, []).append(definition)
    return {
        name: entries[0]
        for name, entries in found.items()
        if len({(entry.variable, entry.body_latex) for entry in entries}) == 1
    }


def split_asks(statement: str) -> tuple[str, ...]:
    """The asks in a part, in order, without writing instructions ("and write a sentence") or final periods."""
    trimmed = _WRITING_CLAUSE.sub("", plain_text(statement))
    pieces = (piece.strip().rstrip(".").strip() for piece in _SENTENCE_BREAK.split(trimmed))
    return tuple(piece for piece in pieces if piece)


def without_writing_ask(statement: str) -> str:
    """The statement without "write a sentence..." instructions, which are graded separately and never shown to a model.

    A model that is asked for a sentence it cannot see would call correct math incomplete.
    """
    trimmed = _WRITING_CLAUSE.sub("", statement).strip()
    return trimmed or statement


def ask_label(ask: str) -> str:
    """The ask without its verb: "Compute v'(0)" gives "v'(0)"."""
    return _ASK_PREFIX.sub("", ask, count=1)


def missing_definitions(statement: str, context: str) -> tuple[str, ...]:
    """Function names the statement uses that neither the shared setup nor the statement defines."""
    defined = parse_definitions(" ".join(part for part in (context, statement) if part))
    called = dict.fromkeys(_CALLED.findall(plain_text(statement)))
    return tuple(name for name in called if name not in defined)
