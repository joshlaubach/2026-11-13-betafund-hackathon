"""The topic picker: the bank grouped course -> unit -> topic.

The bank-derived shape (titles and usable flags) is built once per process and
cached. echo_checked is recomputed from the build directory on every call, so a
gate rerun shows up without a restart. Returned dicts are always new objects.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Union

from core import bank_fallback
from scripts.audit_bank import classify, load_bank


class BaseTopic(NamedTuple):
    id: str
    title: str
    usable: bool


class BaseUnit(NamedTuple):
    unit: str
    topics: tuple[BaseTopic, ...]


class BaseCourse(NamedTuple):
    course: str
    units: tuple[BaseUnit, ...]


def _build_index(bank: list[dict]) -> tuple[BaseCourse, ...]:
    """Group bank problems by course, unit, and topic. A problem is usable when classify() accepts it."""
    usable_topics = {problem["topic"] for problem in bank if classify(problem) is None}
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for problem in bank:
        units = grouped.setdefault(problem["course"], {})
        topics = units.setdefault(problem["unit"], {})
        topics.setdefault(problem["topic"], problem["topic_title"])
    return tuple(
        BaseCourse(
            course=course,
            units=tuple(
                BaseUnit(
                    unit=unit,
                    topics=tuple(
                        BaseTopic(id=topic_id, title=title, usable=topic_id in usable_topics)
                        for topic_id, title in topics.items()
                    ),
                )
                for unit, topics in units.items()
            ),
        )
        for course, units in grouped.items()
    )


@lru_cache(maxsize=1)
def _cached_index() -> tuple[BaseCourse, ...]:
    """Read the bank once per process. Raises ValueError when the bank cannot be read."""
    return _build_index(load_bank(bank_fallback.BANK_PATH))


def topic_tree(build_dir: Union[str, Path]) -> list[dict]:
    """The picker tree, with echo_checked read fresh from build_dir on each call."""
    echo_checked = bank_fallback.echo_checked_topics(build_dir)
    return [
        {
            "course": course.course,
            "units": [
                {
                    "unit": unit.unit,
                    "topics": [
                        {
                            "id": topic.id,
                            "title": topic.title,
                            "usable": topic.usable,
                            "echo_checked": topic.id in echo_checked,
                        }
                        for topic in unit.topics
                    ],
                }
                for unit in course.units
            ],
        }
        for course in _cached_index()
    ]
