"""FTS5 query construction from natural-language input.

Raw search queries — especially LLM-generated ones — frequently contain
characters that are illegal in FTS5 MATCH syntax (``?``, ``:``, ``-``, ``"``)
and stopwords that hurt BM25 ranking. This module normalises a query into a
safe OR-joined term list so BM25 can rank candidate documents by how many
content terms they overlap with.

The resulting MATCH string is always valid: punctuation is stripped, stop
words are removed, terms are lowercased, and CJK runs are emitted as bigrams
so unicode61's character-by-character tokenisation can still hit them.
"""

from __future__ import annotations

import re

# Minimal English stop list — keep aggressive removal to focus BM25 on the
# content words that distinguish documents.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "done",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "into",
        "onto",
        "about",
        "over",
        "under",
        "after",
        "before",
        "between",
        "through",
        "during",
        "and",
        "or",
        "but",
        "nor",
        "so",
        "yet",
        "if",
        "then",
        "else",
        "as",
        "than",
        "i",
        "me",
        "my",
        "mine",
        "myself",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "we",
        "us",
        "our",
        "ours",
        "ourselves",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "where",
        "when",
        "why",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "not",
        "no",
        "yes",
        "very",
        "also",
        "just",
        "only",
        "even",
        "still",
        "can",
        "could",
        "would",
        "should",
        "shall",
        "will",
        "may",
        "might",
        "must",
        "any",
        "all",
        "some",
        "each",
        "every",
        "many",
        "much",
        "few",
        "more",
        "most",
        "ever",
        "never",
        "always",
        "often",
        "sometimes",
        "again",
    }
)

# Word characters: ASCII letters, digits, and any non-ASCII letter (CJK etc.).
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[À-￿]+")
_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")

# Maximum terms we send to FTS5 — guards against huge LLM queries.
_MAX_TERMS = 32

# Small built-in synonym groups. These are the high-frequency vocabulary
# bridges that survive across most conversational corpora (kid/child,
# buy/purchase, etc.). They are deliberately *general English*, not
# tuned to any benchmark — adding domain-specific terms would be
# teaching-to-the-test.
#
# When a query token appears as a key, every value in the same group is
# OR-joined into the FTS expression so a memory that uses any synonym
# can still match. Porter stemming handles morphology
# ("researched" ↔ "research") on top of this; the synonyms cover *cross*-
# stem semantic equivalence ("kid" ↔ "child") that stemming can't.
_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"kid", "kids", "child", "children", "youngster"}),
    frozenset({"wife", "husband", "spouse", "partner"}),
    frozenset({"mom", "mother", "mum"}),
    frozenset({"dad", "father", "papa"}),
    frozenset({"buy", "bought", "purchase", "got", "acquired"}),
    frozenset({"research", "study", "investigate", "explore", "look"}),
    frozenset({"job", "work", "career", "profession", "occupation"}),
    frozenset({"trip", "travel", "journey", "vacation", "holiday"}),
    frozenset({"home", "house", "apartment", "place", "residence"}),
    frozenset({"car", "vehicle", "auto", "automobile"}),
    frozenset({"hobby", "interest", "pastime", "activity"}),
    frozenset({"happy", "glad", "joyful", "pleased"}),
    frozenset({"sad", "upset", "unhappy", "down"}),
    frozenset({"big", "large", "huge"}),
    frozenset({"small", "little", "tiny"}),
    frozenset({"like", "love", "enjoy", "favorite", "favourite"}),
    frozenset({"dislike", "hate"}),
    frozenset({"start", "begin", "started", "began"}),
    frozenset({"end", "finish", "ended", "finished"}),
    frozenset({"city", "town"}),
    frozenset({"country", "nation"}),
    frozenset({"sick", "ill", "unwell"}),
    frozenset({"doctor", "physician"}),
    frozenset({"school", "college", "university"}),
    frozenset({"book", "novel", "memoir"}),
    frozenset({"movie", "film"}),
    frozenset({"song", "music", "tune"}),
    frozenset({"pet", "dog", "cat", "puppy", "kitty"}),
)

# Token → set of synonyms (incl. the token itself). Built once at import.
_SYNONYM_INDEX: dict[str, frozenset[str]] = {tok: group for group in _SYNONYM_GROUPS for tok in group}


def build_fts_query(raw: str) -> str:
    """Convert a natural-language query into an FTS5-safe MATCH expression.

    The returned string is suitable for ``WHERE memory_fts MATCH ?`` with an
    FTS5 table tokenised by ``porter unicode61``. Returns ``""`` when the
    query contains no extractable content words; callers should treat that
    as "no keyword search".

    Args:
        raw: Raw query string. May contain punctuation, stopwords, CJK runs,
            or be the empty string.

    Returns:
        An OR-joined list of stem-friendly terms, or ``""`` if nothing
        usable was extracted.
    """
    if not raw:
        return ""

    text = raw.lower()
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return ""

    expanded: list[str] = []
    for tok in tokens:
        if _CJK_RE.search(tok):
            # Emit overlapping bigrams so unicode61 (which splits CJK per
            # character) can still match meaningful sequences.
            if len(tok) == 1:
                expanded.append(tok)
            else:
                expanded.extend(tok[i : i + 2] for i in range(len(tok) - 1))
        else:
            expanded.append(tok)

    # Drop stopwords for English-style tokens; keep numeric tokens (years,
    # versions) and short content words.
    filtered = [t for t in expanded if t not in _STOPWORDS and (len(t) > 1 or t.isdigit())]
    if not filtered:
        # All content was stopwords — fall back to the raw token list so we
        # still issue *some* query rather than no keyword search at all.
        filtered = expanded

    # Deduplicate while preserving order; cap at _MAX_TERMS.
    seen: set[str] = set()
    deduped: list[str] = []
    for t in filtered:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)
        if len(deduped) >= _MAX_TERMS:
            break

    # Expand each token with its synonym group (small, general English).
    # We rebuild the emitted set from scratch so the original deduped
    # tokens are always present even when they share a synonym group
    # with an already-emitted term.
    expanded = []
    emitted: set[str] = set()
    for t in deduped:
        if t not in emitted:
            emitted.add(t)
            expanded.append(t)
        group = _SYNONYM_INDEX.get(t)
        if group:
            for syn in group:
                if syn not in emitted:
                    emitted.add(syn)
                    expanded.append(syn)
        if len(expanded) >= _MAX_TERMS * 2:
            break

    return " OR ".join(expanded)
