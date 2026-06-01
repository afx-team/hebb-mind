"""Tests for query sanitization."""

from __future__ import annotations

from hebb.retrieval.query_sanitizer import (
    _extract_intent,
    _extract_question,
    _strip_tool_artifacts,
    _strip_xml_tags,
    _truncate_to_tail,
    sanitize_query,
)


class TestSanitizeQuery:
    def test_passthrough_short_clean(self):
        assert sanitize_query("What is Python?") == "What is Python?"

    def test_passthrough_empty(self):
        assert sanitize_query("") == ""

    def test_passthrough_none(self):
        assert sanitize_query(None) is None

    def test_passthrough_whitespace_only(self):
        assert sanitize_query("   ") == "   "

    def test_strips_system_reminder(self):
        raw = "<system-reminder>You are helpful</system-reminder>What color is the sky?"
        result = sanitize_query(raw)
        assert "<system-reminder>" not in result
        assert "What color is the sky?" in result

    def test_strips_command_message(self):
        raw = "<command-message>run tool</command-message>Find my notes about Python"
        result = sanitize_query(raw)
        assert "<command-message>" not in result

    def test_preserves_math_angle_brackets(self):
        raw = "Is x < 5 and y > 3?"
        assert sanitize_query(raw) == raw

    def test_strips_code_fences(self):
        raw = "Search for related code\n```python\ndef foo(): pass\n```\nWhat functions use this pattern?"
        result = sanitize_query(raw)
        assert "```" not in result
        assert "What functions use this pattern?" in result

    def test_strips_json_tool_call(self):
        raw = '{"type": "tool_call", "name": "search"}\nWhat is the capital of France?'
        result = sanitize_query(raw)
        assert "tool_call" not in result
        assert "France" in result

    def test_extracts_last_question(self):
        raw = "A" * 600 + " Is this question one? What is the real question?"
        result = sanitize_query(raw)
        assert result == "What is the real question?"

    def test_extracts_intent(self):
        raw = "A" * 250 + " Find all memories about the database migration."
        result = sanitize_query(raw)
        assert "Find all memories about the database migration" in result

    def test_tail_truncation_fallback(self):
        # No question, no intent — should truncate
        raw = "A" * 1000
        result = sanitize_query(raw)
        assert len(result) <= 500

    def test_real_world_mcp_query(self):
        raw = (
            "<system-reminder>You are a memory assistant. "
            "Use search_memory to find relevant memories.</system-reminder>\n"
            '```json\n{"tool": "search_memory"}\n```\n'
            "When did we decide to switch to GraphQL?"
        )
        result = sanitize_query(raw)
        assert "system-reminder" not in result
        assert "GraphQL" in result

    def test_nested_tags(self):
        raw = (
            "<thinking>Let me search for this</thinking>"
            "<system-reminder>context here</system-reminder>"
            "What is the deployment process?"
        )
        result = sanitize_query(raw)
        assert "What is the deployment process?" in result
        assert "<thinking>" not in result


class TestStripXmlTags:
    def test_removes_system_reminder(self):
        text = "<system-reminder>text</system-reminder>query"
        assert _strip_xml_tags(text) == "textquery"

    def test_removes_self_closing(self):
        text = "<tool_result />rest"
        assert _strip_xml_tags(text) == "rest"

    def test_preserves_unknown_tags(self):
        # Tags not in our whitelist should remain
        text = "use <b>bold</b> text"
        assert _strip_xml_tags(text) == "use <b>bold</b> text"

    def test_preserves_comparison(self):
        text = "check if x < 10"
        assert _strip_xml_tags(text) == "check if x < 10"


class TestStripToolArtifacts:
    def test_removes_code_fences(self):
        text = "before\n```\ncode\n```\nafter"
        assert "```" not in _strip_tool_artifacts(text)

    def test_removes_json_tool(self):
        text = 'prefix {"type": "tool_call"} suffix'
        result = _strip_tool_artifacts(text)
        assert "tool_call" not in result
        assert "prefix" in result

    def test_preserves_normal_json(self):
        # JSON without tool keys should remain
        text = ' {"count": 5, "items": []}'
        assert _strip_tool_artifacts(text) == text


class TestExtractQuestion:
    def test_finds_question(self):
        text = "Some context. What is the answer to life?"
        assert _extract_question(text) == "What is the answer to life?"

    def test_returns_none_for_no_question(self):
        assert _extract_question("No question here.") is None

    def test_ignores_short_fragment(self):
        # "Why?" is too short (< 10 chars) to be a real question
        assert _extract_question("Why?") is None

    def test_picks_last_question(self):
        text = "Is this one? No. What about this longer question here?"
        assert _extract_question(text) == "What about this longer question here?"


class TestExtractIntent:
    def test_finds_search_intent(self):
        result = _extract_intent("Please search for Python tutorials")
        assert result is not None
        assert "search" in result.lower()

    def test_finds_what_intent(self):
        result = _extract_intent("What is the deployment status")
        assert result is not None
        assert "deployment" in result

    def test_returns_none_for_no_intent(self):
        assert _extract_intent("The weather is nice today.") is None


class TestTruncateToTail:
    def test_short_text_unchanged(self):
        assert _truncate_to_tail("short", 100) == "short"

    def test_truncates_long_text(self):
        text = "A" * 1000
        result = _truncate_to_tail(text, 500)
        assert len(result) <= 500
