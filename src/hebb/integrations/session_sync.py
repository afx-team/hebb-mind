"""Discover and sync local coding-agent sessions into Hebb Mind."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from hebb.integrations._project import detect_project_name
from hebb.integrations.claude_code.transcript import (
    TurnRecord,
    format_turn_memory,
)
from hebb.integrations.claude_code.transcript import (
    extract_turns as extract_claude_turns,
)
from hebb.integrations.codex.transcript import (
    CodexTurn,
)
from hebb.integrations.codex.transcript import (
    extract_turns as extract_codex_turns,
)
from hebb.models.memory import MemoryCreate, MemoryMetadata

AgentHost = Literal["codex", "claude_code"]
HIPPOCAMPUS_PARTITION = "mem_hippocampus"


@dataclass(frozen=True)
class AgentTurn:
    """A normalized turn ready to become a Hebb memory."""

    session_id: str
    turn: int
    content: str
    timestamp: str | None
    tools: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSession:
    """A local Codex or Claude Code session transcript."""

    id: str
    host: AgentHost
    path: str
    session_id: str
    project: str | None
    updated_at: float
    turns: list[AgentTurn]

    @property
    def turn_count(self) -> int:
        """Return how many syncable turns were parsed."""
        return len(self.turns)

    @property
    def latest_timestamp(self) -> str | None:
        """Return the latest parsed turn timestamp, if present."""
        for turn in reversed(self.turns):
            if turn.timestamp:
                return turn.timestamp
        return None


def discover_sessions(host: AgentHost | None = None, limit: int | None = None) -> list[AgentSession]:
    """Discover local Codex and Claude Code session transcripts.

    Args:
        host: Optional host filter: ``"codex"`` or ``"claude_code"``.
        limit: Optional maximum sessions to inspect after sorting by file modification time.

    Returns:
        Parsed sessions with at least one syncable user-to-assistant turn.
    """
    paths: list[tuple[AgentHost, Path]] = []
    if host in (None, "codex"):
        paths.extend(("codex", path) for path in _codex_session_paths())
    if host in (None, "claude_code"):
        paths.extend(("claude_code", path) for path in _claude_session_paths())

    paths.sort(key=lambda item: _mtime(item[1]), reverse=True)
    sessions: list[AgentSession] = []
    selected_paths = paths if limit is None else paths[: max(limit, 0)]
    for item_host, path in selected_paths:
        session = _load_session(item_host, path)
        if session and session.turn_count:
            sessions.append(session)
    return sessions


def to_memory_create(session: AgentSession, turn: AgentTurn, importance_score: float = 4.0) -> MemoryCreate:
    """Convert one parsed session turn into a memory create request.

    Args:
        session: Parent agent session.
        turn: Parsed turn to store.
        importance_score: Importance score assigned to imported turns.

    Returns:
        A ``MemoryCreate`` targeting the hippocampus working partition.
    """
    metadata = {
        "session_id": session.session_id,
        "turn": turn.turn,
        "host": session.host,
        "tools": turn.tools,
        "mcps": turn.mcps,
        "source_path": session.path,
    }
    if turn.timestamp:
        metadata["timestamp"] = turn.timestamp

    return MemoryCreate(
        content=turn.content[:10000],
        partition_id=HIPPOCAMPUS_PARTITION,
        importance_score=importance_score,
        tags=[session.project] if session.project else [],
        metadata=MemoryMetadata.model_validate(metadata),
        source=f"sync:{session.host}",
    )


def turn_key(host: str, session_id: str, turn: int) -> tuple[str, str, int]:
    """Return the stable dedupe key for a host/session/turn tuple."""
    return (host, session_id, turn)


def session_fingerprint(host: AgentHost, path: Path) -> str:
    """Return a stable short id for a local transcript path.

    Args:
        host: Agent host that owns the transcript.
        path: Transcript path.

    Returns:
        A deterministic opaque id safe to pass through the web console.
    """
    return hashlib.sha256(f"{host}:{path.resolve()}".encode()).hexdigest()[:16]


def _codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    return Path(override).expanduser() if override else Path.home() / ".codex"


def _claude_home() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".claude"


def _codex_session_paths() -> list[Path]:
    home = _codex_home()
    candidates: list[Path] = []
    for pattern in (
        "archived_sessions/*.jsonl",
        "sessions/**/*.jsonl",
        "session/**/*.jsonl",
    ):
        candidates.extend(path for path in home.glob(pattern) if path.is_file())
    return _dedup_paths(candidates)


def _claude_session_paths() -> list[Path]:
    root = _claude_home() / "projects"
    if not root.is_dir():
        return []
    # Claude Code stores primary transcripts directly below each project slug.
    # Subagent transcripts live below nested ``subagents`` directories and are
    # intentionally skipped because they are internal sidechain execution logs.
    return _dedup_paths(path for path in root.glob("*/*.jsonl") if path.is_file())


def _dedup_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def _load_session(host: AgentHost, path: Path) -> AgentSession | None:
    try:
        parsed = _parse_turns(host, path)
    except OSError:
        return None
    if not parsed:
        return None

    first = parsed[0]
    session_id = _turn_session_id(first) or path.stem
    cwd = _turn_cwd(first)
    turns = [_to_agent_turn(item, session_id) for item in parsed]
    return AgentSession(
        id=session_fingerprint(host, path),
        host=host,
        path=str(path),
        session_id=session_id,
        project=_project_label(cwd),
        updated_at=_mtime(path),
        turns=turns,
    )


def _parse_turns(host: AgentHost, path: Path) -> list[TurnRecord] | list[CodexTurn]:
    if host == "codex":
        return extract_codex_turns(path)
    return extract_claude_turns(path)


def _to_agent_turn(item: TurnRecord | CodexTurn, session_id: str) -> AgentTurn:
    turn_index = item.summary.turn if item.summary.turn is not None else 0
    return AgentTurn(
        session_id=session_id,
        turn=turn_index,
        content=format_turn_memory(item.summary, session_id=session_id, timestamp=item.timestamp),
        timestamp=item.timestamp,
        tools=item.summary.tools,
        mcps=item.summary.mcps,
    )


def _turn_session_id(item: TurnRecord | CodexTurn) -> str | None:
    return item.session_id


def _turn_cwd(item: TurnRecord | CodexTurn) -> str | None:
    return item.cwd


def _project_label(cwd: str | None) -> str | None:
    if not cwd:
        return None
    detected = detect_project_name(cwd)
    if detected:
        return detected
    name = Path(cwd).name
    return name or None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
