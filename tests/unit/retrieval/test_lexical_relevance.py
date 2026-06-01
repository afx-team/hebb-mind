"""Tests for calibrated lexical relevance (IDF-weighted query↔content match)."""

from __future__ import annotations

import math

from hebb.retrieval.lexical_relevance import (
    bm25_idf,
    build_lexical_query,
    lexical_relevance,
    make_idf,
    query_surface_tokens,
)


def _rel(query: str, content: str, idf=None) -> float:
    return lexical_relevance(build_lexical_query(query, idf), content)


def test_full_coverage_scores_high():
    """A document containing every query content term covers all the mass."""
    score = _rel("adoption agencies research", "I was researching adoption agencies.")
    assert score >= 0.99


def test_no_overlap_scores_zero():
    score = _rel("quantum entanglement physics", "I love baking sourdough bread.")
    assert score == 0.0


def test_partial_coverage_is_between():
    score = _rel("camping trip in june", "I went camping last summer.")
    assert 0.0 < score < 1.0


def test_idf_weights_rare_terms_higher():
    """With IDF, matching the rare term outweighs matching the common one."""
    # 'group' is common (high df), 'lgbtq' is rare (low df).
    idf = make_idf({"group": 900, "lgbtq": 3, "support": 400}, total_docs=1000)
    only_rare = _rel("lgbtq support group", "the lgbtq community", idf)
    only_common = _rel("lgbtq support group", "our hiking group meets weekly", idf)
    assert only_rare > only_common


def test_score_is_absolute_not_distributional():
    """Same (query, doc) yields the same score regardless of other candidates —
    the score is an absolute content comparison, not a normalised rank."""
    q = build_lexical_query("blue bicycle", make_idf({"blue": 50, "bicycle": 5}, 1000))
    a = lexical_relevance(q, "she rode her blue bicycle to work")
    b = lexical_relevance(q, "she rode her blue bicycle to work")
    assert a == b


def test_stemming_matches_inflections():
    # query 'studies' should match document 'study' and vice versa.
    assert _rel("she studies biology", "I study biology") >= 0.99


def test_synonym_partial_credit():
    """A synonym in the doc earns partial (not full, not zero) credit."""
    # 'kid' <-> 'child' are in a synonym group.
    full = _rel("my kid plays soccer", "my kid plays soccer")
    syn = _rel("my kid plays soccer", "my child plays soccer")
    none = _rel("my kid plays soccer", "my dog plays soccer")
    assert full > syn > none


def test_quoted_phrase_lifts_score():
    """An exact quoted phrase present lifts a generic-overlap score upward."""
    with_phrase = _rel("did they mention 'machine learning'", "we discussed machine learning at length")
    without = _rel("did they mention 'machine learning'", "we discussed cooking at length")
    assert with_phrase > without
    assert with_phrase >= 0.6


def test_person_name_lift():
    has_name = _rel("what did Caroline say", "Caroline said she was happy")
    no_name = _rel("what did Caroline say", "the weather said it would rain")
    assert has_name > no_name


def test_proximity_phrase_beats_scattered():
    """With the same (partial) set of terms matched, a contiguous phrase
    outscores a scattered match — token-distance is weighted, not just set
    membership. (At full coverage both legitimately reach 1.0, so we test the
    partial-coverage case where proximity is the differentiator.)"""
    q = "alpha beta gamma delta"  # 4 content terms; docs match 3 of them
    phrase = _rel(q, "alpha beta gamma everywhere")
    scattered = _rel(q, "alpha cat beta dog gamma fish")
    assert phrase > scattered
    assert scattered > 0.0  # coverage alone would tie them at 0.75


def test_complete_contiguous_match_is_one():
    assert _rel("blue bicycle helmet", "blue bicycle helmet") >= 0.99


def test_proximity_needs_two_terms():
    """A single matched term gets no proximity lift (no distance to measure)."""
    # one content term; coverage 1.0 already, proximity must not push >1.
    assert _rel("bicycle", "i love my bicycle") <= 1.0
    assert _rel("bicycle", "i love my bicycle") >= 0.99


def test_min_cover_span_basic():
    from hebb.retrieval.lexical_relevance import _min_cover_span
    # adjacent positions → span = count-1
    assert _min_cover_span([[2], [3], [4]]) == 2
    # one term far away widens the span
    assert _min_cover_span([[0], [1], [50]]) == 50
    # picks the tightest window across multiple occurrences: 9,10,11 → span 2
    assert _min_cover_span([[0, 10], [11], [9, 12]]) == 2


def test_empty_query_or_content_is_zero():
    assert _rel("", "anything") == 0.0
    assert _rel("something", "") == 0.0
    # all-stopword query has no content terms
    assert _rel("the and of", "the and of") == 0.0


def test_score_bounded_unit_interval():
    for q, c in [
        ("a b c", "a b c d e"),
        ("rare term", "rare rare rare term term"),
        ("'exact phrase' here Bob", "exact phrase Bob exact phrase"),
    ]:
        s = _rel(q, c)
        assert 0.0 <= s <= 1.0


def test_bm25_idf_monotonic_in_rarity():
    """Rarer terms (lower df) get higher IDF; a term in every doc → ~0."""
    rare = bm25_idf(1, 1000)
    common = bm25_idf(500, 1000)
    everywhere = bm25_idf(1000, 1000)
    assert rare > common > everywhere
    assert everywhere >= 0.0  # never negative
    assert math.isclose(everywhere, math.log(1.0 + 0.5 / 1000.5), rel_tol=1e-6)


def test_make_idf_unseen_term_treated_as_rare():
    idf = make_idf({"common": 900}, total_docs=1000)
    assert idf("neverseen") > idf("common")


def test_query_surface_tokens_drops_stopwords_keeps_content():
    toks = query_surface_tokens("When did Caroline go to the LGBTQ support group?")
    assert "caroline" in toks
    assert "lgbtq" in toks
    assert "support" in toks
    assert "group" in toks
    assert "the" not in toks and "did" not in toks
