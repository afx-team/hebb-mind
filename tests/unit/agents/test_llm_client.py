"""Tests for LLMClient._parse_json robustness (backed by the json-repair lib).

Regression for the live incident where GLM-5.1 (under response_format=json_object)
returned a valid object wrapped in DOUBLED outer braces ``{{ ... }}``. That is
invalid JSON, so consolidation parsed it as ``{}`` -> "produced no output
memories; keeping N source" -> the inbox never drained and the same substantive
content was re-sent to the LLM every run.

These also pin the contract relied on elsewhere: a strict-valid response is
returned unchanged; an unrecoverable response collapses to ``{}`` (never a
scalar/list), so callers can distinguish parse failure (``{}``) from a
deliberate empty (``{"memories": []}``).
"""

from __future__ import annotations

from hebb.agents.llm_client import LLMClient

parse = LLMClient._parse_json


def test_plain_json_unchanged() -> None:
    assert parse('{"memories": [{"consolidated_content": "x"}]}')["memories"][0]["consolidated_content"] == "x"


def test_doubled_outer_braces_recovered() -> None:
    """The exact GLM-5.1 failure mode: {{ ... }} with single-brace inner items."""
    raw = '{{\n    "memories": [\n        {"target_partition": "mem_semantic", "consolidated_content": "a fact"}\n    ],\n    "reasoning": "ok"\n}}'
    out = parse(raw)
    assert list(out.keys()) == ["memories", "reasoning"]
    assert len(out["memories"]) == 1
    assert out["memories"][0]["consolidated_content"] == "a fact"


def test_doubled_braces_empty_memories() -> None:
    assert parse('{{"memories": []}}') == {"memories": []}


def test_doubled_braces_inside_code_fence() -> None:
    raw = '```json\n{{"memories": [{"consolidated_content": "y"}]}}\n```'
    assert parse(raw)["memories"][0]["consolidated_content"] == "y"


def test_valid_json_with_double_brace_in_string_not_corrupted() -> None:
    """A legitimate value containing '{{' (e.g. a Jinja template) must survive —
    the raw parse succeeds first, so the brace-collapse repair never runs."""
    out = parse('{"consolidated_content": "use {{ var }} in templates", "tags": ["jinja"]}')
    assert out["consolidated_content"] == "use {{ var }} in templates"
    assert out["tags"] == ["jinja"]


def test_prose_around_object_extracted() -> None:
    assert parse('Here is the result: {"memories": []} done')["memories"] == []


def test_single_quotes_repaired() -> None:
    assert parse("{'memories': []}") == {"memories": []}


def test_truncated_response_recovered() -> None:
    """A response cut off at max_tokens is repaired rather than dropped — the
    hand-rolled parser returned {} here; json-repair closes the structure."""
    raw = '{"memories": [{"consolidated_content": "abc def", "tags": ["x"'
    out = parse(raw)
    assert isinstance(out, dict)
    assert "memories" in out and len(out["memories"]) == 1
    assert out["memories"][0]["consolidated_content"] == "abc def"


def test_trailing_comma_repaired() -> None:
    assert parse('{"memories": [],}') == {"memories": []}


def test_unparseable_returns_empty_dict() -> None:
    # Garbage -> {} (the agent then KEEPS the source; never deletes on parse fail).
    assert parse("not json at all <<<") == {}
    assert parse("") == {}


def test_empty_object_has_no_memories_key() -> None:
    # Distinguishes parse-failure ({}) from deliberate empty ({"memories": []}).
    assert "memories" not in parse("{}")
