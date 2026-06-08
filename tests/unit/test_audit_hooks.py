"""Audit regression tests for Claude Code hook robustness (lane I-hooks).

Covers three confirmed defects:

- F2: a response-shape drift in the recall result must not raise out of
  ``recall.handle_prompt`` / ``recall.handle`` into the host.
- F6: a long active session must not starve cross-session recall — the
  filter-then-truncate is replaced by an adaptive over-fetch.
- F4: a re-fired Stop for the same final turn must not double-write a memory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hebb.integrations.claude_code import recall, stop


class _FakeResponse:
    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _RecallClient:
    """Fake HTTP client whose /search payload can vary per ``top_k`` page."""

    def __init__(self, pages: dict[int, dict] | None = None, payload: dict | None = None) -> None:
        # ``pages`` maps a requested top_k → response payload, letting a test
        # model the adaptive over-fetch. ``payload`` is the fixed fallback.
        self.pages = pages or {}
        self.payload = payload or {}
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def post(self, path: str, json: dict | None = None) -> _FakeResponse:
        self.calls.append((path, json))
        top_k = (json or {}).get("top_k")
        if top_k in self.pages:
            return _FakeResponse(self.pages[top_k])
        return _FakeResponse(self.payload)

    def close(self) -> None:
        self.closed = True


class _StopClient:
    """Fake HTTP client supporting GET (dedup scan) and POST (write)."""

    def __init__(self, existing_items: list[dict] | None = None) -> None:
        self.existing_items = existing_items or []
        self.get_calls: list[tuple[str, dict | None]] = []
        self.post_calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def get(self, path: str, params: dict | None = None) -> _FakeResponse:
        self.get_calls.append((path, params))
        return _FakeResponse({"items": self.existing_items})

    def post(self, path: str, json: dict | None = None) -> _FakeResponse:
        self.post_calls.append((path, json))
        # Newly written memory becomes visible to subsequent dedup scans, so a
        # second Stop in the same process sees it (models the persisted store).
        meta = (json or {}).get("metadata", {})
        self.existing_items.insert(0, {"metadata": meta})
        return _FakeResponse(json)

    def close(self) -> None:
        self.closed = True


def _mem(session_id: str, content: str = "x", **extra: object) -> dict:
    return {
        "score": 0.9,
        "memory": {
            "partition_id": "mem_hippocampus",
            "content": content,
            "tags": [],
            "metadata": {"session_id": session_id},
            **extra,
        },
    }


# ---------------------------------------------------------------------------
# F2 — malformed search response must not raise out of the hook
# ---------------------------------------------------------------------------


class TestRecallMalformedResponse:
    def test_missing_memory_key_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # A result dict with no "memory" key — the old code did r["memory"].
        client = _RecallClient(payload={"results": [{"score": 0.9}]})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "tell me something useful"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        # Must not raise.
        recall.handle_prompt()
        # Nothing emitted (no usable content), and the client was closed.
        assert capsys.readouterr().out == ""
        assert client.closed is True

    def test_missing_content_key_is_skipped_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # One result lacks "content"; the other is well-formed.
        bad = {"score": 0.9, "memory": {"partition_id": "p", "tags": [], "metadata": {}}}
        good = _mem("old", content="usable cross-session fact")
        client = _RecallClient(payload={"results": [bad, good]})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "what did we decide earlier?"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        out = capsys.readouterr().out
        # Bad entry skipped, good entry emitted, count reflects only the good one.
        assert "usable cross-session fact" in out
        assert 'count="1"' in out

    def test_non_dict_memory_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # "memory" is a string, not a dict — .get would explode on the old path.
        client = _RecallClient(payload={"results": [{"score": 0.9, "memory": "oops"}]})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "give me prior context"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        assert capsys.readouterr().out == ""

    def test_results_not_a_list_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # "results" is the wrong type entirely.
        client = _RecallClient(payload={"results": None})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "anything relevant?"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        assert capsys.readouterr().out == ""

    def test_session_start_handle_also_guarded(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        client = _RecallClient(payload={"results": [{"score": 0.9}]})
        monkeypatch.setattr(recall, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(recall, "get_client", lambda timeout=20: client)
        recall.handle()
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# F6 — adaptive over-fetch when the active session starves the page
# ---------------------------------------------------------------------------


class TestRecallAdaptiveOverfetch:
    def test_overfetches_when_current_session_dominates_first_page(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # First page (top_k=20) is full but every hit is the current session,
        # so the filter leaves 0. A larger page (top_k=40) surfaces a mix that
        # yields >= _TOP_K_RETURN cross-session results.
        page20 = {"results": [_mem("s1") for _ in range(20)]}
        page40 = {
            "results": [_mem("s1") for _ in range(20)]
            + [_mem("old", content=f"cross fact {i}") for i in range(20)]
        }
        client = _RecallClient(pages={20: page20, 40: page40})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "recall my earlier work please"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        out = capsys.readouterr().out
        # It re-issued the search with a bigger page.
        requested = [c[1]["top_k"] for c in client.calls]
        assert requested == [20, 40]
        # Exactly _TOP_K_RETURN cross-session results emitted, none current.
        assert f'count="{recall._TOP_K_RETURN}"' in out
        assert "cross fact" in out

    def test_stops_overfetching_when_service_returns_short_page(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # The service has only 3 cross-session memories total. The page comes
        # back shorter than requested, so a bigger fetch cannot help — the loop
        # must terminate after one call rather than spin to the ceiling.
        page = {"results": [_mem("old", content=f"fact {i}") for i in range(3)]}
        client = _RecallClient(payload=page)
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "what do you remember about me?"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        out = capsys.readouterr().out
        assert [c[1]["top_k"] for c in client.calls] == [20]
        assert 'count="3"' in out

    def test_respects_overfetch_ceiling(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # Every page is full and entirely current-session: the loop must never
        # exceed _TOP_K_FETCH_MAX, then give up with no output.
        full_current = {"results": [_mem("s1") for _ in range(recall._TOP_K_FETCH_MAX)]}
        client = _RecallClient(payload=full_current)
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "surface anything from before"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        requested = [c[1]["top_k"] for c in client.calls]
        # 20 → 40 → 80 → 100 (ceiling), then stop.
        assert requested[0] == 20
        assert requested[-1] == recall._TOP_K_FETCH_MAX
        assert max(requested) == recall._TOP_K_FETCH_MAX
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# F4 — duplicate Stop for the same turn must not double-write
# ---------------------------------------------------------------------------


def _write_transcript(tmp_path: Path) -> Path:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "Explain this code"}]},
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "It does X."}]},
            }
        )
        + "\n"
    )
    return transcript


class TestStopIdempotency:
    def test_duplicate_stop_same_turn_does_not_double_write(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        transcript = _write_transcript(tmp_path)
        client = _StopClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)

        # First Stop writes the turn.
        stop.handle()
        # Re-fired Stop for the exact same final turn must be a no-op.
        stop.handle()

        assert len(client.post_calls) == 1
        _, payload = client.post_calls[0]
        assert payload["metadata"]["session_id"] == "s1"
        assert payload["metadata"]["turn"] == 0

    def test_pre_existing_duplicate_blocks_first_write(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # The store already holds this session+turn (e.g. a prior process
        # crashed after the write). The new Stop must detect it and skip.
        transcript = _write_transcript(tmp_path)
        client = _StopClient(existing_items=[{"metadata": {"session_id": "s1", "turn": 0}}])
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert client.post_calls == []

    def test_different_turn_still_writes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # A stored memory for turn 0 must not block a write for turn 1.
        transcript = _write_transcript(tmp_path)
        client = _StopClient(existing_items=[{"metadata": {"session_id": "s1", "turn": 1}}])
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert len(client.post_calls) == 1

    def test_different_session_still_writes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # Same turn index but a different session must not be treated as a dup.
        transcript = _write_transcript(tmp_path)
        client = _StopClient(existing_items=[{"metadata": {"session_id": "other", "turn": 0}}])
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert len(client.post_calls) == 1

    def test_dedup_scan_failure_does_not_block_write(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # If the dedup GET blows up, the write must still proceed — the guard
        # must never block a genuine write.
        transcript = _write_transcript(tmp_path)

        class _ExplodingGetClient(_StopClient):
            def get(self, path: str, params: dict | None = None) -> _FakeResponse:
                raise RuntimeError("service down")

        client = _ExplodingGetClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert len(client.post_calls) == 1
