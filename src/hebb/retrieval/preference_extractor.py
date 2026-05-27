"""Preference / state / nostalgia extraction from user utterances.

When the user writes "I've been having trouble with my sleep schedule"
or "我最近一直在为睡眠问题烦恼", ingest emits an additional synthetic
memory of the form ``"User has mentioned: <phrase>"`` keyed against
the same partition. The synthetic doc is short and query-friendly —
it stands a much better chance of being retrieved when the question
is "what sleep issues did the user mention?" / "用户说过自己什么困扰？"
than the long original utterance buried in a session.

Pattern catalog:
    English — 21 patterns reproduced verbatim from MemPalace's
        hybrid_v4 list (16 base + 5 nostalgia). Authored by reading
        LongMemEval / ConvoMem question wording.
    Chinese — 14 patterns added for Hebb's bilingual user base.
        Cover preference (我喜欢/我比较喜欢), intent (我想/我打算),
        habit (我经常/我一般), concern (我担心/我有困扰), memory
        (我记得/我以前/小时候), and recency (我最近/最近一直).
        Authored by surveying common conversational openers in
        Chinese personal-memory contexts; we don't have a public
        Chinese benchmark yet to tune them against.

Both halves are dataset-vocabulary-dependent and will silently no-op
on out-of-distribution domains (code, technical docs). Each pattern
captures the phrase after the trigger and emits one synthetic doc.
"""

from __future__ import annotations

import re

_MAX_PER_UTTERANCE = 12
_MIN_LEN_EN = 5
_MIN_LEN_CN = 2
_MAX_LEN = 80

PREF_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        # English — 16 base patterns from MemPalace hybrid_v4
        r"i(?:'ve been| have been) having (?:trouble|issues?|problems?) with ([^,\.!?]{5,80})",
        r"i(?:'ve been| have been) feeling ([^,\.!?]{5,60})",
        r"i(?:'ve been| have been) (?:struggling|dealing) with ([^,\.!?]{5,80})",
        r"i(?:'ve been| have been) (?:worried|concerned) about ([^,\.!?]{5,80})",
        r"i(?:'m| am) (?:worried|concerned) about ([^,\.!?]{5,80})",
        r"i prefer ([^,\.!?]{5,60})",
        r"i usually ([^,\.!?]{5,60})",
        r"i(?:'ve been| have been) (?:trying|attempting) to ([^,\.!?]{5,80})",
        r"i(?:'ve been| have been) (?:considering|thinking about) ([^,\.!?]{5,80})",
        r"i want to ([^,\.!?]{5,60})",
        r"i(?:'m| am) looking (?:to|for) ([^,\.!?]{5,60})",
        r"i(?:'m| am) thinking (?:about|of) ([^,\.!?]{5,60})",
        r"lately[,\s]+(?:i've been|i have been|i'm|i am) ([^,\.!?]{5,80})",
        r"recently[,\s]+(?:i've been|i have been|i'm|i am) ([^,\.!?]{5,80})",
        r"i(?:'ve been| have been) (?:working on|focused on|interested in) ([^,\.!?]{5,80})",
        r"i(?:'ve been| have been) (?:noticing|experiencing) ([^,\.!?]{5,80})",
        # English — 5 nostalgia patterns
        r"i (?:still )?remember (?:the |my )?([^,\.!?]{5,80})",
        r"i used to ([^,\.!?]{5,60})",
        r"when i was (?:in high school|in college|young|a kid|growing up)[,\s]+([^,\.!?]{5,80})",
        r"growing up[,\s]+([^,\.!?]{5,80})",
        r"(?:happy|fond|good|positive) (?:high school|college|childhood|school) (?:experience|memory|memories|time)",
        # Chinese — 14 patterns
        r"我(?:比较)?喜欢([^，。！？\n]{2,30})",
        r"我更倾向于([^，。！？\n]{2,30})",
        r"我(?:一般|经常|平时|通常)([^，。！？\n]{2,30})",
        r"我(?:想要|打算|准备)([^，。！？\n]{2,30})",
        r"我(?:在|正在)考虑([^，。！？\n]{2,30})",
        r"我希望([^，。！？\n]{2,30})",
        r"我担心([^，。！？\n]{2,30})",
        r"我(?:对|在)([^，。！？\n]{2,15})(?:有|存在)(?:困扰|烦恼|问题|担心)",
        r"我最近一直在(?:为|因为)([^，。！？\n]{2,30})(?:烦恼|发愁|担心)",
        r"我最近([^，。！？\n]{2,30})",
        r"最近我([^，。！？\n]{2,30})",
        r"我(?:还)?记得([^，。！？\n]{2,30})",
        r"我以前([^，。！？\n]{2,30})",
        r"小时候(?:我)?([^，。！？\n]{2,30})",
    )
)

_CJK_CHECK_RE = re.compile(r"[一-鿿]")


def _is_predominantly_cjk(text: str) -> bool:
    """True when ≥50 % of characters are in the CJK block."""
    if not text:
        return False
    cjk = len(_CJK_CHECK_RE.findall(text))
    return cjk * 2 >= len(text)


def extract_preferences(text: str) -> list[str]:
    """Return deduped preference / state / nostalgia phrases from ``text``.

    Each returned phrase is a cleaned regex capture (trailing
    punctuation stripped, length re-checked against the per-script
    minimum). The list preserves first-occurrence order so synthetic
    docs follow the user's narrative.

    Patterns are applied to the *original-cased* text for Chinese
    (CJK is caseless) but lowercased for English (the English regexes
    are written in lowercase). We run two passes over the catalog
    rather than try to unify casing — clearer and the overhead is
    negligible.
    """
    phrases: list[str] = []
    seen: set[str] = set()
    lowered = text.lower()
    for pat in PREF_PATTERNS:
        haystack = text if _is_predominantly_cjk(text) else lowered
        for match in pat.findall(haystack):
            phrase = match if isinstance(match, str) else " ".join(match)
            clean = phrase.strip().rstrip(".,;!? 。，；！？")
            min_len = _MIN_LEN_CN if _is_predominantly_cjk(clean) else _MIN_LEN_EN
            if len(clean) < min_len or len(clean) > _MAX_LEN:
                continue
            if clean in seen:
                continue
            seen.add(clean)
            phrases.append(clean)
            if len(phrases) >= _MAX_PER_UTTERANCE:
                return phrases
    return phrases


def synthesize_preference_memory(phrase: str) -> str:
    """Format a single preference phrase as a retrieval-friendly memory.

    The ``"User has mentioned: …"`` prefix is what MemPalace settled on
    after iterating — it embeds well as a short standalone declarative
    sentence regardless of the embedding model. Keeping the wording
    identical keeps head-to-head numbers attributable to the pattern
    set rather than the phrasing.
    """
    return f"User has mentioned: {phrase}"
