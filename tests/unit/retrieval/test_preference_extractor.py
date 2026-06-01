"""Unit tests for preference / nostalgia phrase extraction."""

from __future__ import annotations

from hebb.retrieval.preference_extractor import (
    PREF_PATTERNS,
    extract_preferences,
    synthesize_preference_memory,
)


def test_pref_patterns_count_matches_v4_plus_chinese():
    """21 English (MemPalace hybrid_v4) + 14 Chinese (Hebb addition)."""
    assert len(PREF_PATTERNS) == 21 + 14


def test_extract_concern_pattern():
    """Pattern captures everything up to the sentence terminator."""
    phrases = extract_preferences("I've been having trouble with my sleep schedule for weeks now.")
    assert any("my sleep schedule" in p for p in phrases)


def test_extract_preference_pattern():
    phrases = extract_preferences("I prefer dark roast coffee in the morning.")
    assert any("dark roast coffee" in p for p in phrases)


def test_extract_habit_pattern():
    phrases = extract_preferences("I usually go to bed at 11pm on weeknights.")
    assert any("go to bed at 11pm" in p for p in phrases)


def test_extract_intent_pattern():
    phrases = extract_preferences("I want to learn how to play the piano.")
    assert any("learn how to play the piano" in p for p in phrases)


def test_extract_nostalgia_memory_pattern():
    phrases = extract_preferences("I still remember the day we went hiking in Yosemite together.")
    assert any("day we went hiking" in p for p in phrases)


def test_extract_used_to_pattern():
    phrases = extract_preferences("I used to play volleyball in high school.")
    assert any("play volleyball in high school" in p for p in phrases)


def test_extract_growing_up_pattern():
    phrases = extract_preferences("Growing up, we spent every summer at the lake.")
    assert any("we spent every summer at the lake" in p for p in phrases)


def test_extract_returns_empty_for_neutral_text():
    """A factual statement without preference signals should yield no phrases."""
    assert extract_preferences("The capital of France is Paris.") == []


def test_extract_handles_empty_text():
    assert extract_preferences("") == []


def test_extract_dedupes_repeated_phrases():
    phrases = extract_preferences("I prefer chocolate ice cream. I prefer chocolate ice cream.")
    assert len(phrases) == 1


def test_extract_caps_at_max_per_utterance():
    """A ranty user message must not spew more than 12 synthetic docs."""
    chunks = " ".join(f"I prefer thing number {i:02d}." for i in range(15))
    phrases = extract_preferences(chunks)
    assert len(phrases) <= 12


def test_extract_rejects_too_short_captures():
    """Patterns require ≥5 char captures after cleanup."""
    assert extract_preferences("I prefer ab.") == []


def test_extract_truncates_at_pattern_cap():
    """The regex's own {N,M} cap is the upper bound — captures past it are
    truncated, not rejected. Long ranty utterances yield a single capped
    phrase rather than dropping the match.
    """
    long = "I prefer " + "x" * 81
    phrases = extract_preferences(long)
    assert len(phrases) == 1
    assert 0 < len(phrases[0]) <= 60


def test_synthesize_preference_memory_uses_canonical_prefix():
    """The 'User has mentioned: …' prefix must be stable across runs.

    Changing this string requires re-running every benchmark — the
    embeddings of synthetic docs are sensitive to this prefix.
    """
    assert synthesize_preference_memory("dark roast") == "User has mentioned: dark roast"


def test_chinese_preference_pattern():
    phrases = extract_preferences("我喜欢深烘焙的咖啡")
    assert any("深烘焙" in p for p in phrases)


def test_chinese_habit_pattern():
    phrases = extract_preferences("我一般晚上十一点睡觉")
    assert any("晚上十一点" in p for p in phrases)


def test_chinese_intent_pattern():
    phrases = extract_preferences("我打算学习弹钢琴")
    assert any("学习弹钢琴" in p for p in phrases)


def test_chinese_concern_pattern():
    phrases = extract_preferences("我担心自己的睡眠质量")
    assert any("睡眠质量" in p for p in phrases)


def test_chinese_recency_pattern():
    phrases = extract_preferences("我最近一直在跑步锻炼")
    assert any("跑步锻炼" in p for p in phrases)


def test_chinese_nostalgia_pattern():
    phrases = extract_preferences("小时候我在乡下度过了暑假")
    assert any("乡下度过" in p or "在乡下度过了暑假" in p for p in phrases)


def test_chinese_dedup():
    """Repeated Chinese utterances dedupe just like English."""
    cn_phrases = [p for p in extract_preferences("我喜欢咖啡。我喜欢咖啡。") if "咖啡" in p]
    assert len(cn_phrases) == 1


def test_neutral_chinese_text_yields_nothing():
    """A statement without preference signals must not trigger patterns."""
    assert extract_preferences("法国的首都是巴黎。") == []
