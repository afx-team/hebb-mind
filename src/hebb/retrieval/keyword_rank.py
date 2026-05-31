"""Blend re-ranking for the keyword channel — lift top-1/top-k beyond raw BM25.

The keyword channel is *ranking*-limited, not generation-limited: the right
memory is almost always in the BM25 candidate pool (Recall@50 ≈ 0.99 across
LoCoMo / LongMemEval / MemBench) but BM25 ranks it too low. BM25 on short
conversational docs ignores two cheap, strong signals:

  * **coverage**  — how many *distinct* query content-terms the doc contains
  * **proximity** — how tightly those matched terms cluster (phrase-ness),
    measured by the smallest document window covering them

We keep BM25 as the backbone (min-max normalized magnitude — the magnitude,
not just rank position, is what protects the true #1 from being flipped by a
lower-ranked doc that merely has higher coverage) and multiply by a bounded
boost ``1 + cov_w·coverage + prox_w·proximity``. Tuned weights (0.8 / 0.8) lift
keyword-only top-1 by +2-3pp on every dataset tested — a *universal* gain,
unlike synonym/phrase tweaks which were dataset-dependent washes.

No corpus IDF / DB round-trips needed: coverage and proximity are computed from
the query terms and the candidate's own text, so this is ~free at query time.
"""

from __future__ import annotations

from hebb.models.memory import Memory
from hebb.retrieval.lexical_relevance import _content_tokens, _min_cover_span, build_lexical_query

# Default boost weights (validated sweet spot across LoCoMo/LongMemEval/MemBench).
DEFAULT_COVERAGE_WEIGHT = 0.8
DEFAULT_PROXIMITY_WEIGHT = 0.8


def blend_keyword_rank(
    query: str,
    candidates: list[tuple[Memory, float]],
    *,
    coverage_weight: float = DEFAULT_COVERAGE_WEIGHT,
    proximity_weight: float = DEFAULT_PROXIMITY_WEIGHT,
) -> list[tuple[Memory, float]]:
    """Re-rank BM25 keyword candidates by BM25-magnitude × coverage/proximity boost.

    Args:
        query: The (sanitized) query string.
        candidates: ``[(Memory, bm25_magnitude)]`` where ``bm25_magnitude`` is a
            larger-is-better BM25 relevance magnitude (SQLite ``|bm25|``,
            PostgreSQL ``ts_rank``). Order is not relied upon.
        coverage_weight: Boost weight for query-term coverage.
        proximity_weight: Boost weight for matched-term proximity (phrase-ness).

    Returns:
        ``[(Memory, blended_score)]`` sorted best-first. ``blended_score`` is a
        ranking score (≥ 0), not a calibrated [0, 1] relevance.
    """
    if len(candidates) <= 1:
        return [(m, 1.0) for m, _ in candidates]

    qterms = build_lexical_query(query).terms  # stemmed content terms (unit-weighted)
    nq = len(qterms) or 1

    mags = [mag for _, mag in candidates]
    lo, hi = min(mags), max(mags)
    span = (hi - lo) or 1.0

    scored: list[tuple[Memory, float]] = []
    for memory, mag in candidates:
        bm25n = (mag - lo) / span  # [0, 1], 1 = strongest BM25 in pool

        toks = _content_tokens(memory.content)
        positions: dict[str, list[int]] = {}
        for i, t in enumerate(toks):
            positions.setdefault(t, []).append(i)

        matched = [positions[t] for t in qterms if t in positions]
        coverage = len(matched) / nq
        if len(matched) >= 2:
            sp = _min_cover_span(matched)
            ideal = len(matched) - 1
            proximity = 1.0 if sp <= ideal else ideal / sp
        else:
            proximity = 0.0

        score = bm25n * (1.0 + coverage_weight * coverage + proximity_weight * proximity)
        scored.append((memory, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
