"""Tests for core/retrieval.py. Offline only: reads docs/verified_problems.json, no network, no model."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core import retrieval  # noqa: E402
from core.bank_fallback import BANK_PATH  # noqa: E402
from core.retrieval import (  # noqa: E402
    _load_index,
    eligible_topic_ids,
    normalize_latex,
    search,
    tokenize,
)
from scripts.audit_bank import classify, load_bank  # noqa: E402

RESULT_KEYS = {
    "topic",
    "topic_title",
    "problem_id",
    "level",
    "statement",
    "steps",
    "answer_latex",
    "score",
}
HIT_RATE_FLOOR = 0.80
# Student-style queries and the bank topic each should retrieve in its top three results.
RELEVANCE_CASES = [
    ("how do I use the chain rule on the square root of x squared", "chain_rule"),
    ("derivative of a fraction where x is on top and x plus one is on the bottom", "quotient_rule"),
    ("product rule for x times sine of x", "product_rule"),
    ("power rule derivative of x to the fifth power", "power_rule"),
    ("find the limit by factoring and canceling the common factor", "algebraic"),
    ("limit as x goes to infinity of a rational function", "at_infinity"),
    ("u substitution to integrate x times e to the x squared", "u_substitution"),
    ("integral of cosine with a substitution u equals sin x", "u_substitution"),
    ("how fast is the radius changing when a balloon is inflated, related rates", "related_rates"),
    ("implicit differentiation of x squared plus y squared equals 25", "implicit"),
    ("find the equation of the tangent line to the curve at a point", "tangent_normal_lines"),
    ("volume of a solid by disks rotated about the x axis", "volume_disk_washer"),
    ("integration by parts for the integral of x times ln x", "by_parts"),
    ("use the limit definition of the derivative of x squared", "limit_definition"),
    ("maximize the area of a rectangle with a fixed perimeter", "optimization"),
    ("L'Hopital's rule for a 0 over 0 limit", "lhopital"),
    ("intermediate value theorem to show a root exists between two points", "ivt"),
    ("Newton's method to approximate a root", "newtons_method"),
    ("geometric series sum with ratio one half", "geometric"),
    ("p-series convergence for 1 over n to the p", "p_series"),
    ("Taylor series of e to the x around zero", "taylor_maclaurin"),
    ("derivative of ln x", "exponential_log"),
    ("integral of sine cubed x", "trig_integrals"),
    ("arc length of the curve y equals f of x", "arc_length"),
    ("one-sided limit from the right of a piecewise function", "one_sided"),
    ("derivative of arctan x", "inverse_trig"),
]


def eligible_problems() -> list[dict]:
    return [problem for problem in load_bank(BANK_PATH) if classify(problem) is None]


def topics_in_course(course: str) -> set[str]:
    return {problem["topic"] for problem in eligible_problems() if problem["course"] == course}


# ---------------------------------------------------------------------------
# Tokenizing LaTeX and words
# ---------------------------------------------------------------------------


def test_normalize_turns_frac_into_the_word_frac():
    assert "frac" in normalize_latex(r"\frac{1}{x}").split()


def test_normalize_turns_int_into_the_word_integral():
    assert "integral" in tokenize(r"\int x\,dx")


def test_normalize_turns_caret_into_the_word_power():
    assert "power" in tokenize("x^{2}")


def test_normalize_drops_dollars_and_braces():
    text = normalize_latex("$\\frac{x}{2}$")

    assert "$" not in text and "{" not in text and "}" not in text


def test_tokenize_lowercases_and_drops_stopwords_and_digits():
    assert tokenize("How do I find the Chain 2 rule") == ["chain", "rule"]


def test_tokenize_of_only_stopwords_is_empty():
    assert tokenize("how do I find the") == []


def test_synonym_differentiate_maps_to_derivative():
    assert tokenize("differentiate") == ["derivative"]


def test_synonym_antiderivative_maps_to_integral():
    assert tokenize("antiderivative") == ["integral"]


def test_synonym_u_sub_maps_to_substitution():
    assert tokenize("u-sub") == ["substitution"]


def test_synonym_lim_maps_to_limit():
    assert tokenize(r"\lim_{x \to 0}") == ["limit"]


def test_phrase_chain_rule_adds_composite():
    assert "composite" in tokenize("chain rule")


# ---------------------------------------------------------------------------
# The index: eligible problems only
# ---------------------------------------------------------------------------


def test_index_holds_exactly_the_eligible_problems():
    index = _load_index()

    assert len(index.documents) == len(eligible_problems())


def test_index_has_one_document_per_topic_and_id():
    keys = [(document.topic, document.problem_id) for document in _load_index().documents]

    assert len(keys) == len(set(keys))


def test_index_is_built_once_and_cached():
    assert _load_index() is _load_index()


def test_eligible_topic_ids_match_the_eligible_bank():
    expected = {problem["topic"] for problem in eligible_problems()}

    assert eligible_topic_ids() == frozenset(expected)


def test_search_never_returns_an_ineligible_problem():
    eligible_keys = {(problem["topic"], str(problem["id"])) for problem in eligible_problems()}

    for result in search("integral of x times e to the x", k=5):
        assert (result["topic"], result["problem_id"]) in eligible_keys


# ---------------------------------------------------------------------------
# Result shape and ordering
# ---------------------------------------------------------------------------


def test_result_has_exactly_the_documented_keys():
    results = search("chain rule", k=1)

    assert set(results[0]) == RESULT_KEYS


def test_results_are_sorted_by_score_descending():
    results = search("limit of a rational function at infinity", k=3)
    scores = [result["score"] for result in results]

    assert scores == sorted(scores, reverse=True)


def test_ties_are_ordered_by_problem_id():
    results = search("derivative", k=10)
    ordered = sorted(results, key=lambda result: (-result["score"], result["problem_id"], result["topic"]))

    assert results == ordered


def test_same_query_gives_the_same_order_every_time():
    first = search("u substitution integral", k=3)
    second = search("u substitution integral", k=3)

    assert first == second


def test_search_returns_at_most_k_results():
    assert len(search("derivative rule", k=2)) == 2


def test_empty_query_returns_nothing():
    assert search("   ") == []


def test_query_with_no_matching_term_returns_nothing():
    assert search("zzqqxx") == []


def test_non_string_query_is_rejected():
    with pytest.raises(ValueError):
        search(None)


@pytest.mark.parametrize("k", [0, -1, True, 2.0])
def test_bad_k_is_rejected(k):
    with pytest.raises(ValueError):
        search("chain rule", k=k)


def test_bad_level_is_rejected():
    with pytest.raises(ValueError):
        search("chain rule", level=5)


# ---------------------------------------------------------------------------
# Filters and exclusions
# ---------------------------------------------------------------------------


def test_topic_filter_returns_only_that_topic():
    results = search("derivative", topic="power_rule", k=3)

    assert results and all(result["topic"] == "power_rule" for result in results)


def test_level_filter_returns_only_that_level():
    results = search("derivative", level=2, k=3)

    assert results and all(result["level"] == 2 for result in results)


def test_course_filter_returns_only_that_course():
    results = search("limit", course="calc_ii", k=3)

    assert results
    assert all(result["topic"] in topics_in_course("calc_ii") for result in results)


def test_unknown_topic_falls_back_to_the_course():
    results = search("convergence series", topic="no_such_topic", course="calc_ii", k=3)

    assert results
    assert all(result["topic"] in topics_in_course("calc_ii") for result in results)


def test_unknown_topic_with_no_course_falls_back_to_everything():
    assert search("integral", topic="no_such_topic", k=3) != []


def test_course_filter_does_not_relax_when_it_matches_nothing():
    assert search("integral", course="no_such_course", k=3) == []


def test_exclude_ids_drops_that_problem_from_results():
    top = search("chain rule", k=1)[0]
    excluded = search(
        "chain rule", exclude_ids=[(top["topic"], top["problem_id"])], k=3
    )

    assert all((result["topic"], result["problem_id"]) != (top["topic"], top["problem_id"]) for result in excluded)


def test_exclude_ids_matches_the_topic_and_id_pair_not_the_id_alone():
    top = search("chain rule", k=1)[0]
    other_topic = "no_such_topic"
    kept = search("chain rule", exclude_ids=[(other_topic, top["problem_id"])], k=1)

    assert kept[0]["problem_id"] == top["problem_id"] and kept[0]["topic"] == top["topic"]


def test_exclude_ids_must_be_topic_and_id_pairs():
    with pytest.raises(ValueError):
        search("chain rule", exclude_ids=["CR19"])


# ---------------------------------------------------------------------------
# Relevance eval
# ---------------------------------------------------------------------------


def test_relevance_hit_rate_meets_the_floor_and_is_printed():
    hits = []
    for query, expected_topic in RELEVANCE_CASES:
        top_topics = [result["topic"] for result in search(query, k=3)]
        hits.append(expected_topic in top_topics)
        if expected_topic not in top_topics:
            print(f"  miss: {expected_topic!r} not in top 3 for {query!r}; got {top_topics}")

    rate = sum(hits) / len(hits)
    print(f"retrieval hit rate (expected topic in top 3): {sum(hits)}/{len(hits)} = {rate:.0%}")

    assert rate >= HIT_RATE_FLOOR
