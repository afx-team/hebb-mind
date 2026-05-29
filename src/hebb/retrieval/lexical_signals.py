"""Lexical re-ranking signals — predicate-keyword / quoted-phrase / person-name overlap.

Hybrid retrieval shoring up the embedding+BM25 baseline with three
cheap lexical signals computed at query time:

1. **Predicate keyword overlap** — fraction of query content words
   (≥3 chars, stop-word-free, person-names removed) that appear in the
   candidate memory's text. Strong signal that the memory is on-topic.

2. **Quoted phrase boost** — when the query contains text in single or
   double quotes, candidates that contain the EXACT phrase get a much
   larger boost than predicate overlap alone would give. Matches the
   common "did the user mention 'X'?" question shape.

3. **Person name boost** — capitalized proper nouns in the query that
   aren't in :data:`NOT_NAMES`. Mirrors a standard NER hybrid signal:
   when a question asks about a specific person, candidates that name
   them are preferred.

Each extractor is a pure function and accepts the raw user-typed
query. :func:`lexical_boost` combines all three into a multiplicative
boost on the composite relevance score (centered at 1.0, capped at the
sum of the configured weights).

Inspired by MemPalace's hybrid_v4 query-side re-ranker, but expressed
multiplicatively on the composite *score* rather than divisively on
the cosine *distance*, which fits the existing
:func:`hebb.retrieval.scorer.compute_composite_score` pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Stop words we strip when extracting predicate keywords. Kept small
# and conservative — anything not on this list is treated as
# content-bearing. Matches MemPalace's STOP_WORDS plus a few
# additions for the kinds of queries Hebb sees in production
# (Claude Code / MCP).
_STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "done",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "get",
        "got",
        "give",
        "gave",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "kind",
        "like",
        "made",
        "make",
        "may",
        "me",
        "might",
        "more",
        "most",
        "my",
        "myself",
        "of",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "out",
        "over",
        "own",
        "prefer",
        "said",
        "same",
        "say",
        "shall",
        "she",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "type",
        "under",
        "until",
        "up",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "yours",
    }
)

# Sentence-initial capitalised words that look like person names but
# aren't. Mirrors MemPalace's NOT_NAMES set verbatim, expanded with the
# remaining months (their list was missing "May").
NOT_NAMES = frozenset(
    {
        "What",
        "When",
        "Where",
        "Who",
        "How",
        "Which",
        "Did",
        "Do",
        "Was",
        "Were",
        "Have",
        "Has",
        "Had",
        "Is",
        "Are",
        "The",
        "My",
        "Our",
        "Their",
        "Can",
        "Could",
        "Would",
        "Should",
        "Will",
        "Shall",
        "May",
        "Might",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "In",
        "On",
        "At",
        "For",
        "To",
        "Of",
        "With",
        "By",
        "From",
        "And",
        "But",
        "I",
        "It",
        "Its",
        "This",
        "That",
        "These",
        "Those",
        "Previously",
        "Recently",
        "Also",
        "Just",
        "Very",
        "More",
    }
)

# Boost weights. Each signal contributes a multiplicative boost
# ``1 + weight * fraction``; the total multiplier is at most
# ``1 + sum(weights)``. The defaults match MemPalace's hybrid_v4
# (50 % predicate, 60 % quoted, 20 % name) so head-to-head
# comparisons attribute the lift to the signal, not the weight.
PREDICATE_WEIGHT = 0.50
QUOTED_WEIGHT = 0.60
NAME_WEIGHT = 0.20

_WORD_RE = re.compile(r"\b[a-z]{3,}\b")
_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,15}\b")

# CJK Unified Ideographs basic block. Catches modern Chinese (and
# Japanese kanji, which is fine — they just won't match anything in a
# Chinese-only corpus).
_CJK_RUN_RE = re.compile(r"[一-鿿]{2,}")

# Top-100 single-character Chinese surnames (~85 % census coverage).
# Used as a conservative gate for the Chinese name extractor:
# arbitrary CJK runs are too easy to confuse with regular vocabulary,
# so we only treat a 2-3 char run as a name when its first character
# is a known surname. Misses uncommon surnames; the trade-off is
# zero false-positives on vocabulary.
_CN_SURNAMES = frozenset(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘"
    "于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹"
    "薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
)

# Chinese function tokens (function words + tone particles + common
# pronouns). Removed from predicate-bigram candidates.
_CN_STOP_TOKENS = frozenset(
    {
        "的",
        "了",
        "是",
        "在",
        "和",
        "就",
        "也",
        "都",
        "你",
        "我",
        "他",
        "她",
        "它",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "这些",
        "那些",
        "什么",
        "怎么",
        "哪里",
        "哪个",
        "为什么",
        "如何",
        "可以",
        "应该",
        "可能",
        "或者",
        "但是",
        "因为",
        "所以",
        "如果",
        "虽然",
        "已经",
        "正在",
        "还有",
        "没有",
        "不是",
        "对吧",
        "好的",
        "嗯",
        "哦",
        "啊",
        "吧",
        "呢",
        "吗",
    }
)

# Quote pairs we recognise. Each row is a single regex matching the
# content between the open and close marker. ASCII quotes share a
# character on both sides; typographic and Chinese quotes use distinct
# open/close glyphs. CJK pairs accept ≥2-char content because Chinese
# quoted expressions are dense.
_QUOTED_RES = (
    re.compile(r"'([^']{3,80})'"),
    re.compile(r'"([^"]{3,80})"'),
    re.compile(r"“([^”]{3,80})”"),
    re.compile(r"‘([^’]{3,80})’"),
    re.compile(r"「([^」]{2,80})」"),
    re.compile(r"『([^』]{2,80})』"),
)


@dataclass(frozen=True)
class QuerySignals:
    """Pre-extracted lexical signals from one query.

    Built once per :meth:`MemorySearcher.search` call and reused for
    every candidate — extraction is regex-only but still wasteful at
    O(candidates).
    """

    predicate_keywords: tuple[str, ...]
    quoted_phrases: tuple[str, ...]
    person_names: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.predicate_keywords or self.quoted_phrases or self.person_names)


def _cjk_bigrams(run: str) -> list[str]:
    """Character bigrams for a CJK run. Single-char runs return []."""
    if len(run) < 2:
        return []
    return [run[i : i + 2] for i in range(len(run) - 1)]


def extract_predicate_keywords(query: str) -> list[str]:
    """Return content tokens — English words + Chinese character bigrams.

    English: ≥3-char lowercase tokens, stop words and detected person
    names removed.

    Chinese: each ≥2-char CJK run is split into character bigrams.
    Bigrams act as approximate word units; the lexical-boost substring
    check then catches any doc that contains the bigram as a
    substring. Function-token bigrams and bigrams contained in
    detected names are dropped to avoid double-counting against the
    other boost paths.
    """
    if not query:
        return []
    names = {n.lower() for n in extract_person_names(query)}
    name_chars = "".join(names)
    out: list[str] = []
    seen: set[str] = set()

    # English path
    for w in _WORD_RE.findall(query.lower()):
        if w in _STOP_WORDS or w in names or w in seen:
            continue
        seen.add(w)
        out.append(w)

    # Chinese path
    for run in _CJK_RUN_RE.findall(query):
        for bg in _cjk_bigrams(run):
            if bg in _CN_STOP_TOKENS or bg in seen:
                continue
            if name_chars and bg in name_chars:
                continue
            seen.add(bg)
            out.append(bg)

    return out


def extract_quoted_phrases(query: str) -> list[str]:
    """Return phrases inside ASCII / typographic / Chinese quote pairs.

    Accepts ``''`` ``""`` ``""`` ``''`` ``「」`` ``『』``. Minimum
    content length 2 — Chinese quoted expressions are often short
    (``「外卖」``) and should still register.
    """
    if not query:
        return []
    phrases: list[str] = []
    seen: set[str] = set()
    for pat in _QUOTED_RES:
        for m in pat.findall(query):
            cleaned = m.strip()
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            phrases.append(cleaned)
    return phrases


def extract_person_names(query: str) -> list[str]:
    """Return tokens that look like person names (English + Chinese).

    English: 3–15 lowercase letters after a leading capital, not in
    :data:`NOT_NAMES`.

    Chinese: 2- or 3-char CJK runs whose first character is a known
    surname in :data:`_CN_SURNAMES`. Conservative on purpose —
    arbitrary CJK runs are too easy to confuse with regular vocabulary
    (``城市`` is just "city", not a person). Misses uncommon
    surnames, which is the cost of zero false-positives without a
    name-database dep.
    """
    if not query:
        return []
    out: list[str] = []
    seen: set[str] = set()

    # English
    for w in _NAME_RE.findall(query):
        if w in NOT_NAMES:
            continue
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)

    # Chinese: walk each CJK run and pick the longest surname-prefixed
    # window we find at each starting position (prefer 3-char ``陈先生``
    # over the inner 2-char ``先生``).
    for run in _CJK_RUN_RE.findall(query):
        for i, ch in enumerate(run):
            if ch not in _CN_SURNAMES:
                continue
            for length in (3, 2):
                candidate = run[i : i + length]
                if len(candidate) == length and candidate not in seen:
                    seen.add(candidate)
                    out.append(candidate)
                    break

    return out


def extract_query_signals(query: str) -> QuerySignals:
    """Bundle the three extractors so the caller computes signals once."""
    return QuerySignals(
        predicate_keywords=tuple(extract_predicate_keywords(query)),
        quoted_phrases=tuple(extract_quoted_phrases(query)),
        person_names=tuple(extract_person_names(query)),
    )


def lexical_boost(signals: QuerySignals, memory_content: str) -> float:
    """Return a multiplicative score boost in ``[1.0, 1 + sum(weights)]``.

    Each signal contributes ``weight * fraction-of-signal-present`` to
    the multiplier minus 1. Returns ``1.0`` (no boost) when no signals
    were extracted from the query — guards the no-op case so callers
    can apply the multiplier unconditionally.
    """
    if signals.is_empty or not memory_content:
        return 1.0

    doc = memory_content.lower()
    boost = 0.0

    if signals.predicate_keywords:
        hits = sum(1 for kw in signals.predicate_keywords if kw in doc)
        boost += PREDICATE_WEIGHT * (hits / len(signals.predicate_keywords))

    if signals.quoted_phrases:
        hits = sum(1 for p in signals.quoted_phrases if p.lower() in doc)
        boost += QUOTED_WEIGHT * (hits / len(signals.quoted_phrases))

    if signals.person_names:
        hits = sum(1 for n in signals.person_names if n.lower() in doc)
        boost += NAME_WEIGHT * (hits / len(signals.person_names))

    return 1.0 + boost


# ---------------------------------------------------------------------
# Assistant-reference 2-pass trigger
# ---------------------------------------------------------------------

# Trigger phrases on which we do a second-pass retrieval restricted to
# user-prompt memories: when the question is "what did *you* say…?",
# vector similarity over assistant turns drowns out the user turn that
# anchors the session. The user-turn pass uses the original question to
# find the right session, then composite scoring lifts the surrounding
# turn-summary memory which actually carries the assistant text.
ASSISTANT_REFERENCE_TRIGGERS = (
    # English
    "you suggested",
    "you told me",
    "you said",
    "you recommended",
    "you mentioned",
    "you advised",
    "you identified",
    "you proposed",
    "what did you",
    "did you suggest",
    "did you tell",
    "did you mention",
    "can you remind me",
    "do you remember",
    # Chinese — equivalent you-referenced question shapes
    "你之前说",
    "你说过",
    "你提到",
    "你建议",
    "你推荐",
    "你告诉我",
    "你识别",
    "你提议",
    "你刚才",
    "我们之前讨论",
    "我们讨论过",
    "你还记得",
    "记得我们",
    "上次你",
)


def is_assistant_reference_query(query: str) -> bool:
    """True if the query asks about something the assistant previously said."""
    if not query:
        return False
    q = query.lower()
    return any(t in q for t in ASSISTANT_REFERENCE_TRIGGERS)
