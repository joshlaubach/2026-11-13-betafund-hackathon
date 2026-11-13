"""Per-topic skill profile and practice recommendations from graded worksheet items.

Pure functions: no model call, no network, no file write. The bank tree comes from
server/topics.py (read once per process). Inputs are never mutated; every result is
a new frozen object. Standard library plus the shared worksheet_types models.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional, Sequence, Union

from core import bank_fallback
from core.worksheet_types import GradedItem, Recommendation, SkillStatus, TopicSkill
from server.topics import topic_tree

BUILD_DIR = bank_fallback.BUILD_DIR
BuildDir = Union[str, Path]

UNKNOWN = "unknown"
METHOD_BANK_KEY = "bank_key"
VERDICT_CORRECT = "correct"
VERDICT_INCORRECT = "incorrect"

STATUS_SOLID: SkillStatus = "solid"
STATUS_SHAKY: SkillStatus = "shaky"
STATUS_WEAK: SkillStatus = "weak"
STATUS_NOT_ENOUGH_DATA: SkillStatus = "not_enough_data"

MIN_PROBLEMS_FOR_STATUS = 2  # one problem alone is never enough to call a status
MIN_CORRECT_FOR_SOLID = 2  # a single correct mark is not solid

# Lower number is shown first. Solid topics are never recommended.
RECOMMEND_ORDER: dict[str, int] = {
    STATUS_WEAK: 0,
    STATUS_SHAKY: 1,
    STATUS_NOT_ENOUGH_DATA: 2,
}
SUGGESTED_LEVEL: dict[str, int] = {
    STATUS_WEAK: 1,
    STATUS_SHAKY: 2,
    STATUS_NOT_ENOUGH_DATA: 2,
}
DEFAULT_RECOMMEND_COUNT = 3
MIN_RECOMMEND_COUNT = 1


@dataclass(frozen=True)
class Profile:
    """Skills for the topics that appear in the graded items, plus a count of items with no topic."""

    skills: tuple[TopicSkill, ...]
    unplaced: int


@dataclass(frozen=True)
class _Tally:
    correct: int = 0
    incorrect: int = 0
    unsure: int = 0
    verified: int = 0

    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.unsure

    def add(self, graded: GradedItem) -> "_Tally":
        verdict = graded.grade.verdict
        return _Tally(
            correct=self.correct + int(verdict == VERDICT_CORRECT),
            incorrect=self.incorrect + int(verdict == VERDICT_INCORRECT),
            unsure=self.unsure + int(verdict not in (VERDICT_CORRECT, VERDICT_INCORRECT)),
            verified=self.verified + int(graded.grade.method == METHOD_BANK_KEY),
        )


@dataclass(frozen=True)
class _BankTopic:
    course: str
    unit: str
    title: str


class _BankIndex(NamedTuple):
    topics: dict[str, _BankTopic]
    unit_order: dict[tuple[str, str], int]


def _bank_index(build_dir: BuildDir) -> _BankIndex:
    """Topic lookup and course/unit order, both taken from the bank order in server/topics.py."""
    topics: dict[str, _BankTopic] = {}
    unit_order: dict[tuple[str, str], int] = {}
    for course in topic_tree(build_dir):
        for unit in course["units"]:
            unit_order.setdefault((course["course"], unit["unit"]), len(unit_order))
            for topic in unit["topics"]:
                topics.setdefault(
                    topic["id"],
                    _BankTopic(course=course["course"], unit=unit["unit"], title=topic["title"]),
                )
    return _BankIndex(topics=topics, unit_order=unit_order)


def _topic_of(graded: GradedItem) -> Optional[str]:
    """The bank topic for a graded item: the bank key's topic when bank-marked, else the reader's guess."""
    if graded.grade.method == METHOD_BANK_KEY and graded.grade.bank_topic:
        return graded.grade.bank_topic
    return graded.item.topic_guess or None


def _status_for(tally: _Tally) -> SkillStatus:
    if tally.total < MIN_PROBLEMS_FOR_STATUS or (tally.correct == 0 and tally.incorrect == 0):
        return STATUS_NOT_ENOUGH_DATA
    if tally.incorrect == 0:
        if tally.correct >= MIN_CORRECT_FOR_SOLID:
            return STATUS_SOLID
        return STATUS_NOT_ENOUGH_DATA
    if tally.correct >= tally.incorrect:
        return STATUS_SHAKY
    return STATUS_WEAK


def _skill(topic: str, tally: _Tally, bank_topics: dict[str, _BankTopic]) -> TopicSkill:
    info = bank_topics.get(topic)
    return TopicSkill(
        topic=topic,
        title=info.title if info else topic,
        course=info.course if info else UNKNOWN,
        unit=info.unit if info else UNKNOWN,
        correct=tally.correct,
        incorrect=tally.incorrect,
        unsure=tally.unsure,
        status=_status_for(tally),
        verified_marks=tally.verified,
    )


def build_profile(graded: Sequence[GradedItem], build_dir: BuildDir = BUILD_DIR) -> Profile:
    """Count marks per topic. Items with no topic are counted in Profile.unplaced, never dropped."""
    tallies: dict[str, _Tally] = {}
    unplaced = 0
    for graded_item in graded:
        topic = _topic_of(graded_item)
        if topic is None:
            unplaced += 1
            continue
        tallies[topic] = tallies.get(topic, _Tally()).add(graded_item)
    if not tallies:
        return Profile(skills=(), unplaced=unplaced)
    bank_topics = _bank_index(build_dir).topics
    skills = tuple(_skill(topic, tallies[topic], bank_topics) for topic in sorted(tallies))
    return Profile(skills=skills, unplaced=unplaced)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _reason(skill: TopicSkill) -> str:
    total = skill.correct + skill.incorrect + skill.unsure
    if skill.status == STATUS_NOT_ENOUGH_DATA:
        return f"Only {_plural(total, 'problem')} seen, so Echo cannot tell yet; try a few more."
    return (
        f"Got {skill.correct} of {_plural(total, 'problem')} right on this topic "
        f"({_plural(skill.verified_marks, 'verified mark')})."
    )


def _validate_count(count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or count < MIN_RECOMMEND_COUNT:
        raise ValueError(f"count must be a positive integer, got {count!r}")
    return count


def _recommendation(rank: int, skill: TopicSkill, echo_checked: set[str]) -> Recommendation:
    return Recommendation(
        rank=rank,
        topic=skill.topic,
        title=skill.title,
        status=skill.status,
        reason=_reason(skill),
        suggested_level=SUGGESTED_LEVEL[skill.status],
        echo_checked=skill.topic in echo_checked,
    )


def recommend(
    profile: Profile, count: int = DEFAULT_RECOMMEND_COUNT, build_dir: BuildDir = BUILD_DIR
) -> list[Recommendation]:
    """Up to count topics to practice: weak, then shaky, then not_enough_data.

    Within a status, earlier course and unit in the bank order come first, then topic id.
    Solid topics are skipped. Raises ValueError for a non-positive count.
    """
    limit = _validate_count(count)
    candidates = [skill for skill in profile.skills if skill.status in RECOMMEND_ORDER]
    if not candidates:
        return []
    unit_order = _bank_index(build_dir).unit_order
    unknown_position = len(unit_order)
    ordered = sorted(
        candidates,
        key=lambda skill: (
            RECOMMEND_ORDER[skill.status],
            unit_order.get((skill.course, skill.unit), unknown_position),
            skill.topic,
        ),
    )
    echo_checked = bank_fallback.echo_checked_topics(build_dir)
    return [
        _recommendation(rank, skill, echo_checked)
        for rank, skill in enumerate(ordered[:limit], start=1)
    ]


def summarize(profile: Profile) -> dict[str, int]:
    """Status counts plus how many of the placed marks are verified against the bank."""
    statuses = Counter(skill.status for skill in profile.skills)
    problems_seen = sum(skill.correct + skill.incorrect + skill.unsure for skill in profile.skills)
    verified_marks = sum(skill.verified_marks for skill in profile.skills)
    return {
        "solid": statuses[STATUS_SOLID],
        "shaky": statuses[STATUS_SHAKY],
        "weak": statuses[STATUS_WEAK],
        "not_enough_data": statuses[STATUS_NOT_ENOUGH_DATA],
        "problems_seen": problems_seen,
        "verified_marks": verified_marks,
        "ai_marks": problems_seen - verified_marks,
    }
