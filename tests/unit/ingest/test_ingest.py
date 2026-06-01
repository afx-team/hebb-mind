"""Tests for multi-format conversation ingestion."""

from __future__ import annotations

import json

from hebb.ingest.detector import detect_format
from hebb.ingest.formats import (
    parse_chatgpt_json,
    parse_claude_code_jsonl,
    parse_plain_text,
)
from hebb.ingest.noise import strip_noise
from hebb.ingest.normalizer import normalize
from hebb.ingest.types import Format

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_detect_claude_code_jsonl(self):
        raw = '{"type": "human", "content": "hello"}\n{"type": "assistant", "content": "hi"}'
        assert detect_format(raw) == Format.CLAUDE_CODE_JSONL

    def test_detect_claude_code_with_role_key(self):
        raw = '{"role": "user", "content": "hello"}'
        assert detect_format(raw) == Format.CLAUDE_CODE_JSONL

    def test_detect_chatgpt_json(self):
        data = [{"id": "conv1", "mapping": {"node1": {"message": None}}}]
        assert detect_format(json.dumps(data)) == Format.CHATGPT_JSON

    def test_detect_plain_text(self):
        assert detect_format("User: hello\nAssistant: hi") == Format.PLAIN_TEXT

    def test_detect_empty(self):
        assert detect_format("") == Format.PLAIN_TEXT

    def test_detect_malformed_json(self):
        assert detect_format("{invalid json") == Format.PLAIN_TEXT


# ---------------------------------------------------------------------------
# Claude Code JSONL parser
# ---------------------------------------------------------------------------


class TestClaudeCodeParser:
    def test_simple_conversation(self):
        raw = (
            '{"type": "human", "content": "What is Python?"}\n'
            '{"type": "assistant", "content": "A programming language."}'
        )
        turns = parse_claude_code_jsonl(raw)
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[0].content == "What is Python?"
        assert turns[1].role == "assistant"
        assert turns[1].content == "A programming language."

    def test_tool_result_folding(self):
        raw = '{"type": "assistant", "content": "Let me check."}\n{"type": "tool_result", "content": "42"}'
        turns = parse_claude_code_jsonl(raw)
        assert len(turns) == 1
        assert "42" in turns[0].content
        assert turns[0].role == "assistant"

    def test_session_id_preserved(self):
        raw = '{"type": "human", "content": "hi", "session_id": "sess-123"}'
        turns = parse_claude_code_jsonl(raw)
        assert turns[0].session_id == "sess-123"

    def test_content_as_list(self):
        raw = '{"type": "assistant", "content": [{"text": "hello"}, {"text": " world"}]}'
        turns = parse_claude_code_jsonl(raw)
        assert turns[0].content == "hello\n world"

    def test_malformed_lines_skipped(self):
        raw = '{"type": "human", "content": "ok"}\nnot json\n{"type": "assistant", "content": "yes"}'
        turns = parse_claude_code_jsonl(raw)
        assert len(turns) == 2

    def test_empty_content_skipped(self):
        raw = '{"type": "human", "content": ""}\n{"type": "assistant", "content": "real"}'
        turns = parse_claude_code_jsonl(raw)
        assert len(turns) == 1
        assert turns[0].content == "real"


# ---------------------------------------------------------------------------
# ChatGPT JSON parser
# ---------------------------------------------------------------------------


class TestChatGPTParser:
    def _make_conv(self, messages: list[dict]) -> dict:
        mapping = {}
        for i, msg in enumerate(messages):
            mapping[f"node_{i}"] = {
                "message": {
                    "author": {"role": msg["role"]},
                    "content": {"parts": [msg["content"]]},
                    "create_time": 1700000000 + i,
                }
            }
        return {"id": "conv-1", "mapping": mapping}

    def test_single_conversation(self):
        conv = self._make_conv(
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ]
        )
        turns = parse_chatgpt_json(json.dumps([conv]))
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    def test_skips_system_messages(self):
        conv = self._make_conv(
            [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "hello"},
            ]
        )
        turns = parse_chatgpt_json(json.dumps([conv]))
        assert len(turns) == 1
        assert turns[0].role == "user"

    def test_session_id_from_conv_id(self):
        conv = self._make_conv([{"role": "user", "content": "hi"}])
        turns = parse_chatgpt_json(json.dumps([conv]))
        assert turns[0].session_id == "conv-1"

    def test_timestamps_converted(self):
        conv = self._make_conv([{"role": "user", "content": "hi"}])
        turns = parse_chatgpt_json(json.dumps([conv]))
        assert turns[0].timestamp is not None
        assert "T" in turns[0].timestamp  # ISO format


# ---------------------------------------------------------------------------
# Plain text parser
# ---------------------------------------------------------------------------


class TestPlainTextParser:
    def test_role_markers(self):
        raw = "User: hello\nAssistant: world"
        turns = parse_plain_text(raw)
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[0].content == "hello"
        assert turns[1].role == "assistant"

    def test_angle_bracket_markers(self):
        raw = "> what is 2+2\nThe answer is 4."
        turns = parse_plain_text(raw)
        assert len(turns) == 1
        assert turns[0].role == "user"
        assert "what is 2+2" in turns[0].content

    def test_multiline_turns(self):
        raw = "User: line one\ncontinued line\nAssistant: reply"
        turns = parse_plain_text(raw)
        assert len(turns) == 2
        assert "line one\ncontinued line" == turns[0].content

    def test_unmarked_defaults_to_user(self):
        raw = "just some text"
        turns = parse_plain_text(raw)
        assert len(turns) == 1
        assert turns[0].role == "user"

    def test_case_insensitive_markers(self):
        raw = "USER: hi\nASSISTANT: hello"
        turns = parse_plain_text(raw)
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"


# ---------------------------------------------------------------------------
# Noise stripping
# ---------------------------------------------------------------------------


class TestNoiseStripping:
    def test_strip_system_tags(self):
        text = "<system-reminder>context</system-reminder>actual content"
        assert "system-reminder" not in strip_noise(text)
        assert "actual content" in strip_noise(text)

    def test_strip_thinking_tags(self):
        text = "<thinking>internal</thinking>visible"
        result = strip_noise(text)
        assert "<thinking>" not in result
        assert "visible" in result

    def test_strip_env_blocks(self):
        text = "Platform: darwin\nShell: zsh\nActual content here"
        result = strip_noise(text)
        assert "Platform:" not in result
        assert "Actual content here" in result

    def test_preserve_normal_content(self):
        text = "This is perfectly normal text with no noise."
        assert strip_noise(text) == text

    def test_empty_string(self):
        assert strip_noise("") == ""

    def test_collapse_newlines(self):
        text = "before\n\n\n\n\nafter"
        assert strip_noise(text) == "before\n\nafter"


# ---------------------------------------------------------------------------
# End-to-end normalize()
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_claude_code_end_to_end(self):
        raw = '{"type": "human", "content": "hello"}\n{"type": "assistant", "content": "hi"}'
        result = normalize(raw)
        assert result.format_detected == "claude_code"
        assert result.turn_count == 2

    def test_chatgpt_end_to_end(self):
        conv = {
            "id": "c1",
            "mapping": {
                "n1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["hello"]},
                        "create_time": 1700000000,
                    }
                }
            },
        }
        result = normalize(json.dumps([conv]))
        assert result.format_detected == "chatgpt"
        assert result.turn_count == 1

    def test_plain_text_end_to_end(self):
        result = normalize("User: hello\nAssistant: world")
        assert result.format_detected == "plain"
        assert result.turn_count == 2

    def test_format_hint_override(self):
        raw = "not json at all"
        result = normalize(raw, format_hint="plain")
        assert result.format_detected == "plain"

    def test_invalid_format_hint_warns(self):
        result = normalize("User: hi", format_hint="unknown_format")
        assert len(result.warnings) > 0
        assert result.turn_count == 1  # still works via auto-detect

    def test_noise_stripped_from_turns(self):
        raw = '{"type": "human", "content": "<system-reminder>ctx</system-reminder>real question"}'
        result = normalize(raw)
        assert "<system-reminder>" not in result.turns[0].content
        assert "real question" in result.turns[0].content

    def test_empty_turns_filtered(self):
        raw = (
            '{"type": "human", "content": "<system-reminder></system-reminder>"}\n'
            '{"type": "assistant", "content": "real content"}'
        )
        result = normalize(raw)
        # The first turn becomes empty after noise stripping → filtered out
        assert result.turn_count == 1
        assert result.turns[0].role == "assistant"
