"""Date-anchored boost for retrieval candidates.

When a query mentions an absolute date ("August 2023", "May 7 2023",
"in 2022") or a relative phrase ("last month", "N weeks ago",
"yesterday"), boost candidates whose ``metadata.timestamp`` falls near
that date. Returns a multiplicative score boost in ``[0, 0.40]`` per the
MemPalace v2 schedule.

The parser is deliberately small and language-agnostic enough to apply
beyond LoCoMo — it works on plain English month names plus generic
"N units ago" phrases. The reference date for relative phrases is
supplied by the caller (typically the most recent timestamp in the
corpus); without one, relative phrases are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

_MONTH_NAMES: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH_RE = re.compile(r"\b(" + "|".join(_MONTH_NAMES) + r")\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)(\d{2})\b")
_DAY_RE = re.compile(r"\b([0-3]?\d)(?:st|nd|rd|th)?\b")

# Relative phrases
_REL_AGO_RE = re.compile(
    r"\b(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(day|week|month|year)s?\s+ago\b",
    re.IGNORECASE,
)
_REL_LAST_RE = re.compile(
    r"\blast\s+(week|month|year)\b",
    re.IGNORECASE,
)
_YESTERDAY_RE = re.compile(r"\byesterday\b", re.IGNORECASE)

_WORD_NUM = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


@dataclass(frozen=True)
class QueryDate:
    """One date anchor parsed out of a query.

    ``year`` and ``month`` are required; ``day`` may be ``None`` when only
    a month was specified. ``tolerance_days`` widens the proximity
    window — month-only matches get a coarse window, day-precise matches
    get a tight one.
    """

    year: int
    month: int
    day: int | None
    tolerance_days: int


def _parse_absolute(query: str) -> list[QueryDate]:
    out: list[QueryDate] = []
    months = list(_MONTH_RE.finditer(query))
    years = list(_YEAR_RE.finditer(query))

    # Pattern A: "<day> <month> <year>" or "<month> <day> <year>" or "<month> <year>"
    for mm in months:
        month = _MONTH_NAMES[mm.group(1).lower()]
        # closest year token to the right or within 25 chars
        year: int | None = None
        for yr in years:
            if 0 <= yr.start() - mm.end() <= 25 or 0 <= mm.start() - yr.end() <= 25:
                year = int(yr.group(0))
                break
        if year is None:
            continue
        # Look for a day number adjacent to the month name
        day: int | None = None
        window = query[max(0, mm.start() - 15) : mm.end() + 15]
        for dm in _DAY_RE.finditer(window):
            n = int(dm.group(1))
            if 1 <= n <= 31:
                day = n
                break
        tol = 3 if day else 20
        out.append(QueryDate(year=year, month=month, day=day, tolerance_days=tol))

    # Pattern B: "in <year>" (no month) — wider tolerance
    if not out:
        for yr in years:
            year = int(yr.group(0))
            # Avoid duplicate from Pattern A — only add if no month match
            out.append(QueryDate(year=year, month=0, day=None, tolerance_days=180))

    return out


def _parse_relative(query: str, reference: date) -> list[QueryDate]:
    out: list[QueryDate] = []

    for m in _REL_AGO_RE.finditer(query):
        n_raw, unit = m.group(1).lower(), m.group(2).lower()
        n = _WORD_NUM.get(n_raw, None)
        if n is None:
            try:
                n = int(n_raw)
            except ValueError:
                continue
        delta_days = {"day": n, "week": n * 7, "month": n * 30, "year": n * 365}[unit]
        target = reference - timedelta(days=delta_days)
        tol = {"day": 1, "week": 5, "month": 15, "year": 60}[unit]
        out.append(QueryDate(target.year, target.month, target.day, tol))

    for m in _REL_LAST_RE.finditer(query):
        unit = m.group(1).lower()
        delta_days = {"week": 7, "month": 30, "year": 365}[unit]
        target = reference - timedelta(days=delta_days)
        tol = {"week": 5, "month": 15, "year": 60}[unit]
        out.append(QueryDate(target.year, target.month, target.day, tol))

    if _YESTERDAY_RE.search(query):
        target = reference - timedelta(days=1)
        out.append(QueryDate(target.year, target.month, target.day, 1))

    return out


def parse_query_dates(query: str, reference: date | None = None) -> list[QueryDate]:
    """Extract date anchors from a natural-language query.

    Args:
        query: Search query text.
        reference: "Now" date used to ground relative phrases like
            "last week". When ``None``, only absolute dates are parsed.

    Returns:
        Zero or more :class:`QueryDate` anchors.
    """
    if not query:
        return []
    out = _parse_absolute(query)
    if reference is not None:
        out.extend(_parse_relative(query, reference))
    return out


def parse_memory_date(timestamp: str) -> date | None:
    """Best-effort extraction of a calendar date from a free-form timestamp string.

    Recognises ISO (``2023-05-08``), ``25 May, 2023`` /
    ``May 25 2023`` patterns, and any other shape containing a year +
    month name + day.

    Returns ``None`` if no date can be confidently parsed.
    """
    if not timestamp:
        return None

    # ISO first — fastest path.
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", timestamp)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            pass

    year_m = _YEAR_RE.search(timestamp)
    if not year_m:
        return None
    year = int(year_m.group(0))

    month_m = _MONTH_RE.search(timestamp)
    if not month_m:
        return None
    month = _MONTH_NAMES[month_m.group(1).lower()]

    day = 1
    # Pick a day number close to the month name.
    span_start = max(0, month_m.start() - 6)
    span_end = min(len(timestamp), month_m.end() + 6)
    for dm in _DAY_RE.finditer(timestamp[span_start:span_end]):
        n = int(dm.group(1))
        if 1 <= n <= 31:
            day = n
            break

    try:
        return date(year, month, day)
    except ValueError:
        return None


def temporal_boost(
    memory_timestamp: str | None,
    query_dates: list[QueryDate],
    max_boost: float = 0.40,
) -> float:
    """Return a multiplicative score boost in ``[0, max_boost]``.

    Boost is full when the memory's calendar date is within
    ``QueryDate.tolerance_days`` of an anchor and decays linearly to
    zero at ``3 × tolerance_days``. The best (highest) boost across
    anchors wins — multiple anchors do not stack.
    """
    if not query_dates or not memory_timestamp:
        return 0.0

    mem_date = parse_memory_date(memory_timestamp)
    if mem_date is None:
        return 0.0

    best = 0.0
    for qd in query_dates:
        # Anchor month=0 means "year only".
        if qd.month == 0:
            if mem_date.year == qd.year:
                best = max(best, max_boost * 0.5)
            continue

        try:
            target = date(qd.year, qd.month, qd.day or 15)
        except ValueError:
            continue
        delta = abs((mem_date - target).days)
        tol = qd.tolerance_days
        if delta <= tol:
            best = max(best, max_boost)
        elif delta <= tol * 3:
            scaled = max_boost * (1 - (delta - tol) / (tol * 2))
            best = max(best, scaled)

    return best
