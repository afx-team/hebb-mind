"""Unit tests for the lexical-signal extractors and boost function."""

from __future__ import annotations

from hebb.retrieval.lexical_signals import (
    NAME_WEIGHT,
    PREDICATE_WEIGHT,
    QUOTED_WEIGHT,
    extract_person_names,
    extract_predicate_keywords,
    extract_query_signals,
    extract_quoted_phrases,
    is_assistant_reference_query,
    lexical_boost,
)

# ----------------------------------------------------------------------
# Predicate keywords
# ----------------------------------------------------------------------


def test_predicate_keywords_drop_stop_words_and_short_tokens() -> None:
    kws = extract_predicate_keywords("When did the user mention painting hobby?")
    # 'when', 'did', 'the' are stop words; tokens must be ≥3 chars
    assert set(kws) == {"user", "mention", "painting", "hobby"}


def test_predicate_keywords_exclude_person_names() -> None:
    """Names should be credited via the name boost, not the predicate."""
    kws = extract_predicate_keywords("What did Caroline say about painting?")
    assert "caroline" not in kws
    assert "painting" in kws


def test_predicate_keywords_dedup_preserves_order() -> None:
    kws = extract_predicate_keywords("painting painting hobby painting hobby")
    assert kws == ["painting", "hobby"]


def test_predicate_keywords_empty_query() -> None:
    assert extract_predicate_keywords("") == []


# ----------------------------------------------------------------------
# Quoted phrases
# ----------------------------------------------------------------------


def test_quoted_phrases_extracts_both_single_and_double_quotes() -> None:
    q = """Did the user mention 'a complicated relationship' or "sleep schedule"?"""
    phrases = extract_quoted_phrases(q)
    assert "a complicated relationship" in phrases
    assert "sleep schedule" in phrases


def test_quoted_phrases_rejects_too_short() -> None:
    # <3 chars after strip should be rejected
    assert extract_quoted_phrases("the 'a' alone") == []


def test_quoted_phrases_dedup_case_insensitive() -> None:
    phrases = extract_quoted_phrases("'Hello' and 'hello' again")
    assert len(phrases) == 1


# ----------------------------------------------------------------------
# Person names
# ----------------------------------------------------------------------


def test_person_names_extracts_capitalized_proper_nouns() -> None:
    names = extract_person_names("Caroline and Melanie went to the park.")
    assert set(names) == {"Caroline", "Melanie"}


def test_person_names_rejects_not_names_set() -> None:
    """Sentence-initial wh-words, months, weekdays must not count as names."""
    names = extract_person_names("What did Caroline do on Monday in August?")
    assert names == ["Caroline"]


def test_person_names_dedup() -> None:
    names = extract_person_names("Caroline and Caroline and caroline")
    # case-insensitive dedup; preserves first casing
    assert names == ["Caroline"]


# ----------------------------------------------------------------------
# QuerySignals bundle
# ----------------------------------------------------------------------


def test_query_signals_is_empty_when_no_signals() -> None:
    sig = extract_query_signals("the a is")
    assert sig.is_empty


def test_query_signals_is_not_empty_when_anything_extracted() -> None:
    sig = extract_query_signals("Caroline")
    assert not sig.is_empty
    assert sig.person_names == ("Caroline",)


# ----------------------------------------------------------------------
# Lexical boost
# ----------------------------------------------------------------------


def test_lexical_boost_returns_one_when_signals_empty() -> None:
    sig = extract_query_signals("")
    assert lexical_boost(sig, "any memory") == 1.0


def test_lexical_boost_returns_one_when_memory_empty() -> None:
    sig = extract_query_signals("Caroline went painting")
    assert lexical_boost(sig, "") == 1.0


def test_lexical_boost_full_predicate_overlap() -> None:
    """Doc contains all predicate words → boost = 1 + PREDICATE_WEIGHT."""
    sig = extract_query_signals("Where did the user mention painting?")
    # query predicate_kws = {user, mention, painting}
    doc = "the user did mention painting yesterday"
    # All 3 predicates in doc; expected boost = 1 + 0.5 * (3/3)
    boost = lexical_boost(sig, doc)
    assert abs(boost - (1.0 + PREDICATE_WEIGHT)) < 1e-6


def test_lexical_boost_partial_predicate_overlap() -> None:
    sig = extract_query_signals("user mention painting")
    doc = "I love painting"  # 1 of 3 predicates
    boost = lexical_boost(sig, doc)
    assert abs(boost - (1.0 + PREDICATE_WEIGHT / 3)) < 1e-6


def test_lexical_boost_combines_all_three_signals() -> None:
    """Predicate + quoted phrase + name all contribute additively to the boost."""
    sig = extract_query_signals(
        """Did Caroline mention 'a sleep problem' recently?"""
    )
    # predicates: {caroline-out, mention, recently} = {mention, recently}
    # quoted: {'a sleep problem'}
    # names: {Caroline}
    doc = "Caroline did mention a sleep problem to me recently"
    boost = lexical_boost(sig, doc)
    # All 3 signals at 100%: 1 + 0.5 + 0.6 + 0.2 = 2.3
    expected = 1.0 + PREDICATE_WEIGHT + QUOTED_WEIGHT + NAME_WEIGHT
    assert abs(boost - expected) < 1e-6


def test_lexical_boost_zero_overlap_returns_one() -> None:
    sig = extract_query_signals("painting hobby")
    doc = "completely unrelated topic"
    assert lexical_boost(sig, doc) == 1.0


def test_lexical_boost_is_case_insensitive() -> None:
    sig = extract_query_signals("PAINTING")
    assert lexical_boost(sig, "i love painting") > 1.0


# ----------------------------------------------------------------------
# Assistant reference trigger
# ----------------------------------------------------------------------


def test_assistant_reference_query_detects_triggers() -> None:
    assert is_assistant_reference_query("What did you suggest about the diet?")
    assert is_assistant_reference_query("Can you remind me what we discussed?")
    assert is_assistant_reference_query("You told me to try yoga")


def test_assistant_reference_query_negative() -> None:
    assert not is_assistant_reference_query("What did I have for dinner?")
    assert not is_assistant_reference_query("")


# ----------------------------------------------------------------------
# Chinese support
# ----------------------------------------------------------------------


def test_predicate_keywords_chinese_bigrams() -> None:
    """CJK runs produce overlapping character bigrams as predicate tokens."""
    kws = extract_predicate_keywords("用户提到了画画爱好")
    # Stop tokens like '了' are dropped at the bigram level if formed; we
    # check that core content bigrams survive.
    assert "画画" in kws
    assert "爱好" in kws
    assert "用户" in kws


def test_predicate_keywords_chinese_drops_function_tokens() -> None:
    """'的' bigrams that match _CN_STOP_TOKENS must not appear."""
    kws = extract_predicate_keywords("用户的偏好")
    # '的' is a stop token bigram (it's a single char so won't form a
    # bigram on its own anyway). But '用户的' / '户的' / '的偏' could
    # appear — none should leak as '的'.
    assert "的" not in kws


def test_predicate_keywords_mixed_english_chinese() -> None:
    """Bilingual query yields both English words and Chinese bigrams."""
    kws = extract_predicate_keywords("用户 mentioned 画画")
    assert "mentioned" in kws
    assert "画画" in kws


def test_quoted_phrases_chinese_brackets() -> None:
    """Chinese 「」 and 『』 quotes are recognised."""
    phrases = extract_quoted_phrases(
        "用户提到了「外卖」和『午休』这两个话题"
    )
    assert "外卖" in phrases
    assert "午休" in phrases


def test_quoted_phrases_typographic_quotes() -> None:
    """English typographic quotes "" and '' are recognised."""
    phrases = extract_quoted_phrases("did they say “hello world”?")
    assert "hello world" in phrases


def test_person_names_chinese_surname_prefix() -> None:
    """2-3 char CJK runs beginning with a top-100 surname are named candidates."""
    names = extract_person_names("王老师告诉我陈先生最近在忙什么")
    assert "王老师" in names
    assert "陈先生" in names


def test_person_names_chinese_rejects_common_vocabulary() -> None:
    """Arbitrary CJK runs without a surname prefix must NOT be named."""
    names = extract_person_names("城市的发展速度很快")
    # '城' is not in the surname list; no false-positive names.
    assert names == []


def test_lexical_boost_chinese_predicate_overlap() -> None:
    """Chinese bigram overlap lifts the candidate score."""
    sig = extract_query_signals("用户提到画画爱好")
    boost_hit = lexical_boost(sig, "他真的很喜欢画画作为爱好")
    boost_miss = lexical_boost(sig, "今天的天气不错")
    assert boost_hit > 1.0
    assert boost_miss == 1.0


def test_assistant_reference_chinese_triggers() -> None:
    assert is_assistant_reference_query("你之前说过什么饮食建议？")
    assert is_assistant_reference_query("你建议我去哪家餐厅来着")
    assert is_assistant_reference_query("我们之前讨论的方案是哪个")
