"""Calibrated lexical relevance — an absolute [0, 1] query↔content match score.

The keyword channel's BM25 rank tells you *ordering* but not *how relevant*
a memory actually is: BM25 is unbounded, corpus-dependent, and conflates
IDF, term frequency, and document length into one opaque number. Squashing
it with ``1/(1+|bm25|)`` produces a score whose magnitude means nothing —
0.4 might be a perfect match in one query and noise in another.

This module computes relevance the way the goal demands: by *directly
comparing the query against the document text*, independent of the result
set's distribution. The backbone is **IDF-weighted query-term coverage**:

    relevance = Σ idf(t) · matched(t)  /  Σ idf(t)        for t in query terms

so a memory that contains the query's *rare, discriminating* terms scores
high, and one that only shares generic words scores low — regardless of
how many other candidates exist. The result is genuinely calibrated:
0.8 means "the matched terms carry 80 % of the query's IDF mass", the same
thing for every query. Exact quoted-phrase and person-name hits push the
score toward 1.0; a complete miss sits near 0.

IDF is supplied by the caller (computed once per search from corpus
document frequencies) so this module stays pure and free of storage deps.
When no IDF is available every term weighs 1.0 — plain coverage, still a
true content comparison.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# Content tokens: ASCII word runs (letters/digits) and CJK runs. Mirrors
# the families the FTS query builder and lexical-signal extractors handle.
_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[一-鿿]{1,}")

# Imports placed after the module-level regexes (hence noqa: E402).
#  * lexical_signals — reuse its predicate stop list + extractors so query-term
#    extraction is identical across the lexical signals and this scorer.
#  * fts_query — synonym groups mirror the FTS query expander: a query term
#    counts as matched (at a discount) when the doc uses a known synonym.
from hebb.retrieval.fts_query import _SYNONYM_INDEX  # noqa: E402
from hebb.retrieval.lexical_signals import (  # noqa: E402
    _STOP_WORDS,
    extract_person_names,
    extract_quoted_phrases,
)

# A query term matched only through a synonym (not the term itself) counts
# at this fraction of its IDF weight — the bridge is real but weaker than a
# direct hit.
_SYNONYM_CREDIT = 0.5

# Exact quoted-phrase / person-name presence is a strong relevance signal.
# Each lifts the coverage score a fraction of the way to 1.0 (soft-OR), so a
# memory naming the right person or quoted phrase clears a strict floor even
# when the surrounding question words are generic.
_PHRASE_LIFT = 0.6
_NAME_LIFT = 0.4

# Proximity / unquoted-phrase lift. Two query terms that land *adjacent* in the
# document (a phrase) are far stronger evidence than the same two terms 40
# tokens apart, even though set-coverage scores them identically. We measure
# the tightness of the smallest document window covering the matched terms and
# lift the score toward 1.0 in proportion. ``_PROXIMITY_W`` is the max fraction
# of the remaining gap a perfectly contiguous match can close; needs ≥2 matched
# terms (one term has no distance to measure).
_PROXIMITY_W = 0.4

# Minimum English content-term length (shorter alpha tokens are noise; pure
# digits of any length are kept — years, versions, quantities).
_MIN_TERM_LEN = 3


def _stem(token: str) -> str:
    """Cheap deterministic suffix stripper — a dependency-free stand-in for
    Porter so query and document tokens normalise the same way.

    Handles the high-frequency English inflections (plurals, past tense,
    gerunds, comparatives, adverbs) that otherwise split a query term from
    its document form ("studies" ↔ "study", "running" ↔ "run"). Conservative
    by design: only strips when a reasonable stem length remains.
    """
    t = token
    if len(t) > 4:
        for suf in ("ational", "iveness", "fulness", "ousness", "ization", "ization"):
            if t.endswith(suf) and len(t) - len(suf) >= 3:
                return t[: -len(suf)]
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith(("sses", "shes", "ches", "xes")):
        return t[:-2]
    if len(t) > 4 and t.endswith("ing"):
        base = t[:-3]
        return base[:-1] if len(base) > 2 and base[-1] == base[-2] else base
    if len(t) > 4 and t.endswith("ed"):
        base = t[:-2]
        return base[:-1] if len(base) > 2 and base[-1] == base[-2] else base
    if len(t) > 4 and t.endswith("ly"):
        return t[:-2]
    if len(t) > 3 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _content_tokens(text: str) -> list[str]:
    """Stopword-free, stemmed content tokens for an English/CJK string.

    CJK runs are split into character bigrams (mirroring the FTS builder), so
    a query bigram can match a document bigram for languages unicode61
    tokenises per character.
    """
    out: list[str] = []
    low = text.lower()
    for w in _WORD_RE.findall(low):
        if w.isdigit():
            out.append(w)
        elif len(w) >= _MIN_TERM_LEN and w not in _STOP_WORDS:
            out.append(_stem(w))
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


@dataclass(frozen=True)
class LexicalQuery:
    """Pre-parsed query for repeated scoring against many documents.

    Built once per search; ``terms`` are the deduped stemmed content tokens,
    ``raw_terms`` the surface tokens (used to look up IDF the same way FTS
    stems them), ``weights`` the per-term IDF (or 1.0).
    """

    terms: tuple[str, ...]
    weights: tuple[float, ...]
    total_weight: float
    quoted_phrases: tuple[str, ...]
    person_names: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return self.total_weight <= 0.0


def build_lexical_query(
    query: str,
    idf: Callable[[str], float] | None = None,
) -> LexicalQuery:
    """Parse a query into stemmed, IDF-weighted content terms.

    Args:
        query: Raw user query.
        idf: Optional ``raw_token -> idf`` callable. When ``None`` every term
            weighs 1.0 (plain coverage). The IDF is looked up on the *surface*
            token (pre-stem) so it lines up with the corpus document
            frequencies FTS computes on the same surface form.

    Returns:
        A :class:`LexicalQuery` reusable across candidate documents.
    """
    low = query.lower()
    seen: set[str] = set()
    terms: list[str] = []
    weights: list[float] = []
    for w in _WORD_RE.findall(low):
        keep = w.isdigit() or (len(w) >= _MIN_TERM_LEN and w not in _STOP_WORDS)
        if not keep:
            continue
        stem = w if w.isdigit() else _stem(w)
        if stem in seen:
            continue
        seen.add(stem)
        terms.append(stem)
        weights.append(idf(w) if idf is not None else 1.0)
    for run in _CJK_RUN_RE.findall(query):
        bigrams = [run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)]
        for bg in bigrams:
            if bg in seen:
                continue
            seen.add(bg)
            terms.append(bg)
            weights.append(idf(bg) if idf is not None else 1.0)

    total = sum(weights)
    return LexicalQuery(
        terms=tuple(terms),
        weights=tuple(weights),
        total_weight=total,
        quoted_phrases=tuple(extract_quoted_phrases(query)),
        person_names=tuple(extract_person_names(query)),
    )


def _min_cover_span(position_lists: list[list[int]]) -> int:
    """Smallest ``max-min`` window containing ≥1 position from each list.

    Classic "smallest range covering k sorted lists" via a heap of the current
    front of each list. Each list is the document positions of one matched
    query term (non-empty, ascending). Returns the tightest span those terms
    can be found within — 0 when a single position covers all (e.g. duplicates).
    """
    import heapq

    heap: list[tuple[int, int, int]] = []
    cur_max = -1
    for li, lst in enumerate(position_lists):
        heapq.heappush(heap, (lst[0], li, 0))
        cur_max = max(cur_max, lst[0])

    best = cur_max - heap[0][0]
    while True:
        cur_min, li, idx = heapq.heappop(heap)
        best = min(best, cur_max - cur_min)
        if best == 0:
            break
        nxt = idx + 1
        if nxt == len(position_lists[li]):
            break  # this term exhausted → no tighter window possible
        val = position_lists[li][nxt]
        cur_max = max(cur_max, val)
        heapq.heappush(heap, (val, li, nxt))
    return best


def lexical_relevance(lq: LexicalQuery, content: str) -> float:
    """Absolute [0, 1] relevance of ``content`` to the parsed query.

    IDF-weighted coverage of the query's content terms, then lifted toward 1.0
    by (a) **proximity** — matched terms appearing close together / as a phrase,
    measured by the tightest document window covering them; (b) exact
    quoted-phrase hits; (c) person-name hits. A document containing every query
    term scores 1.0; a contiguous phrase match scores higher than the same terms
    scattered. Pure content comparison — no dependence on other candidates.

    Returns ``0.0`` for an empty query or empty content.
    """
    if lq.is_empty or not content:
        return 0.0

    # Ordered tokens → positions per stem. Positions drive the proximity lift;
    # the keys double as the membership set for coverage.
    doc_tokens = _content_tokens(content)
    positions: dict[str, list[int]] = {}
    for i, tok in enumerate(doc_tokens):
        positions.setdefault(tok, []).append(i)
    low_content = content.lower()

    matched = 0.0
    matched_positions: list[list[int]] = []  # one entry per matched query term
    for term, weight in zip(lq.terms, lq.weights, strict=True):
        if term in positions:
            matched += weight
            matched_positions.append(positions[term])
            continue
        # Synonym bridge: the document uses a known synonym of the term.
        group = _SYNONYM_INDEX.get(term)
        if group:
            syn_pos: list[int] = []
            for s in group:
                syn_pos.extend(positions.get(_stem(s), ()))
            if syn_pos:
                matched += weight * _SYNONYM_CREDIT
                matched_positions.append(sorted(syn_pos))

    coverage = matched / lq.total_weight if lq.total_weight > 0 else 0.0
    score = coverage

    # Proximity / unquoted-phrase lift: when ≥2 query terms matched, reward
    # them appearing close together. The smallest document window covering one
    # occurrence of each matched term has span ``max-min``; an ideal contiguous
    # phrase spans ``count-1``. ``proximity = ideal/actual`` → 1.0 when adjacent,
    # decaying with token distance. This is the "分词距离权重" — scattered
    # matches get little lift, phrase matches get the full _PROXIMITY_W.
    if len(matched_positions) >= 2:
        span = _min_cover_span(matched_positions)
        ideal = len(matched_positions) - 1
        proximity = 1.0 if span <= ideal else ideal / span
        score += (1.0 - score) * _PROXIMITY_W * proximity

    # Soft-OR lifts: an exact quoted phrase or named person present is strong
    # standalone evidence. Each closes a fraction of the remaining gap to 1.0.
    if lq.quoted_phrases:
        hit = sum(1 for p in lq.quoted_phrases if p.lower() in low_content)
        if hit:
            frac = hit / len(lq.quoted_phrases)
            score += (1.0 - score) * _PHRASE_LIFT * frac
    if lq.person_names:
        hit = sum(1 for n in lq.person_names if n.lower() in low_content)
        if hit:
            frac = hit / len(lq.person_names)
            score += (1.0 - score) * _NAME_LIFT * frac

    return min(1.0, score)


def bm25_idf(doc_freq: int, total_docs: int) -> float:
    """BM25 IDF for a term, floored at 0.

    ``log((N - df + 0.5) / (df + 0.5) + 1)`` — the Robertson/Spärck-Jones
    form used by SQLite FTS5's own bm25(). Rare terms approach
    ``log(N)``; a term in every document approaches 0. The ``+1`` inside the
    log keeps it non-negative so weights never flip sign.
    """
    if total_docs <= 0:
        return 1.0
    df = max(0, min(doc_freq, total_docs))
    return math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)


def make_idf(
    doc_freqs: dict[str, int],
    total_docs: int,
    *,
    default_df: int = 1,
) -> Callable[[str], float]:
    """Build a ``token -> idf`` callable from precomputed document frequencies.

    Tokens absent from ``doc_freqs`` are treated as rare (``default_df``),
    which is the safe bias: an unseen query term is discriminating, not noise.
    """

    def _idf(token: str) -> float:
        df = doc_freqs.get(token, default_df)
        return bm25_idf(df, total_docs)

    return _idf


def query_surface_tokens(query: str) -> list[str]:
    """Surface (pre-stem) content tokens whose corpus DF the caller should
    look up to weight the query. Matches :func:`build_lexical_query`'s English
    term selection so IDF keys line up with the terms actually scored.
    """
    low = query.lower()
    seen: set[str] = set()
    out: list[str] = []
    for w in _WORD_RE.findall(low):
        if not (w.isdigit() or (len(w) >= _MIN_TERM_LEN and w not in _STOP_WORDS)):
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def cjk_surface_tokens(query: str) -> Iterable[str]:
    """CJK bigram surface tokens for DF lookup (parallel to the English ones)."""
    seen: set[str] = set()
    for run in _CJK_RUN_RE.findall(query):
        bigrams = [run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)]
        for bg in bigrams:
            if bg not in seen:
                seen.add(bg)
                yield bg
