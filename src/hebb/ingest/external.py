"""Import deterministic Markdown memory corpora from other agent frameworks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from hebb.constants import PartitionType
from hebb.ingest.noise import clean_user_input, is_greeting_only

if TYPE_CHECKING:
    from hebb.api import HebbMind

ExternalSource = Literal["openhands", "openclaw", "hkuds"]
SUPPORTED_EXTERNAL_SOURCES: tuple[ExternalSource, ...] = ("openhands", "openclaw", "hkuds")

_PROCEDURAL_CATEGORIES = {"how-to", "howto", "procedure", "procedural", "process", "skill", "workflow"}


class ExternalImportError(ValueError):
    """Raised when an external corpus path or source cannot be imported."""


@dataclass(frozen=True)
class ExternalMemoryEntry:
    """One cleaned external document ready for Hebb Mind storage."""

    content: str
    partition: str
    importance: float
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    source_path: str


@dataclass(frozen=True)
class ImportSummary:
    """Counts returned after importing one external corpus."""

    discovered: int
    imported: int
    skipped_existing: int


def discover_external_entries(source: str, path: str | Path) -> list[ExternalMemoryEntry]:
    """Parse an external Markdown corpus into cleaned memory entries.

    Args:
        source: One of ``openhands``, ``openclaw``, or ``hkuds``.
        path: A corpus directory, repository/workspace root, or one Markdown file.

    Returns:
        Deterministically ordered entries ready to pass to :class:`HebbMind`.

    Raises:
        ExternalImportError: If the source is unsupported, the path is missing,
            or no Markdown files matching that source's layout are found.
    """
    normalized_source = _normalize_source(source)
    root = Path(path).expanduser()
    if not root.exists():
        raise ExternalImportError(f"Import path does not exist: {root}")

    files = _discover_files(normalized_source, root)
    if not files:
        raise ExternalImportError(f"No {normalized_source} Markdown memory files found under {root}")

    entries: list[ExternalMemoryEntry] = []
    for file_path in files:
        try:
            raw = file_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ExternalImportError(f"Could not read {file_path}: {exc}") from exc

        frontmatter, body = _split_frontmatter(raw)
        if normalized_source == "hkuds" and _as_bool(frontmatter.get("disabled")):
            continue

        content = clean_user_input(body)
        if not content or is_greeting_only(content):
            continue

        source_path = _relative_source_path(file_path, root)
        entries.append(
            _build_entry(
                source=normalized_source,
                file_path=file_path,
                source_path=source_path,
                content=content,
                frontmatter=frontmatter,
            )
        )

    return entries


def import_external_corpus(source: str, path: str | Path, mind: HebbMind) -> ImportSummary:
    """Import an external corpus through Hebb Mind's public write facade.

    Existing entries are identified by a deterministic key derived from the
    source document identity and its cleaned content hash. Re-importing an
    unchanged corpus therefore performs no writes.

    Args:
        source: One of ``openhands``, ``openclaw``, or ``hkuds``.
        path: Corpus directory, workspace/repository root, or Markdown file.
        mind: An initialized :class:`~hebb.api.HebbMind` instance.

    Returns:
        Counts for discovered, imported, and already-present entries.

    Raises:
        ExternalImportError: If discovery or parsing fails.
        HebbMindError: If an underlying store or embedding write fails.
    """
    normalized_source = _normalize_source(source)
    entries = discover_external_entries(normalized_source, path)
    existing_keys = _existing_external_keys(mind)
    imported = 0
    skipped = 0

    for entry in entries:
        external_key = str(entry.metadata["external_key"])
        if external_key in existing_keys:
            skipped += 1
            continue
        mind.add(
            entry.content,
            partition=entry.partition,
            importance=entry.importance,
            tags=list(entry.tags),
            metadata=entry.metadata,
            source=f"external_memory:{normalized_source}",
        )
        existing_keys.add(external_key)
        imported += 1

    return ImportSummary(discovered=len(entries), imported=imported, skipped_existing=skipped)


def _normalize_source(source: str) -> ExternalSource:
    value = source.strip().lower()
    if value not in SUPPORTED_EXTERNAL_SOURCES:
        choices = ", ".join(SUPPORTED_EXTERNAL_SOURCES)
        raise ExternalImportError(f"Unsupported import source {source!r}; choose one of: {choices}")
    return value


def _discover_files(source: ExternalSource, root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".md" else []
    if source == "openhands":
        return _discover_openhands_files(root)
    if source == "openclaw":
        return _discover_openclaw_files(root)
    return _discover_hkuds_files(root)


def _discover_openhands_files(root: Path) -> list[Path]:
    bases = [
        root / ".openhands" / "skills",
        root / ".openhands" / "microagents",
        root / ".agents" / "skills",
    ]
    if root.name.lower() == ".openhands":
        bases.extend((root / "skills", root / "microagents"))
    if root.name.lower() in {"skills", "microagents"}:
        bases.append(root)

    files = {
        path.resolve(): path
        for base in bases
        if base.is_dir()
        for path in base.rglob("*.md")
        if path.name.lower() != "readme.md"
    }
    return sorted(files.values(), key=lambda item: item.as_posix().lower())


def _discover_openclaw_files(root: Path) -> list[Path]:
    workspaces = [root]
    nested_workspace = root / ".openclaw" / "workspace"
    if nested_workspace.is_dir():
        workspaces.append(nested_workspace)
    if root.name.lower() == ".openclaw" and (root / "workspace").is_dir():
        workspaces.append(root / "workspace")

    files: dict[Path, Path] = {}
    for workspace in workspaces:
        for name in ("MEMORY.md", "USER.md", "SOUL.md"):
            candidate = workspace / name
            if candidate.is_file():
                files[candidate.resolve()] = candidate
        daily_dir = workspace / "memory"
        if daily_dir.is_dir():
            for candidate in daily_dir.glob("*.md"):
                files[candidate.resolve()] = candidate
    return sorted(files.values(), key=lambda item: item.as_posix().lower())


def _discover_hkuds_files(root: Path) -> list[Path]:
    directories = [directory for directory in (root / ".openharness" / "memory", root / "memory") if directory.is_dir()]
    if root.name.lower() == "memory" or not directories:
        directories.append(root)

    files = {
        path.resolve(): path
        for directory in directories
        if directory.is_dir()
        for path in directory.glob("*.md")
        if path.name.lower() != "memory.md"
    }
    return sorted(files.values(), key=lambda item: item.as_posix().lower())


def _build_entry(
    *,
    source: ExternalSource,
    file_path: Path,
    source_path: str,
    content: str,
    frontmatter: dict[str, Any],
) -> ExternalMemoryEntry:
    partition, importance, source_tags = _route_entry(source, file_path, source_path, frontmatter)
    native_id = str(frontmatter.get("id") or "").strip()
    source_identity = native_id or source_path
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    key_payload = f"{source}:{source_identity}\0{content_hash}"
    external_key = hashlib.sha256(key_payload.encode("utf-8")).hexdigest()

    metadata: dict[str, Any] = {
        "external_source": source,
        "external_path": source_path,
        "external_source_key": f"{source}:{source_identity}",
        "external_key": external_key,
        "content_hash": content_hash,
    }
    if native_id:
        metadata["external_native_id"] = native_id
    if "schema_version" in frontmatter:
        metadata["external_schema_version"] = frontmatter["schema_version"]
    if "category" in frontmatter:
        metadata["external_category"] = frontmatter["category"]
    if "type" in frontmatter:
        metadata["external_type"] = frontmatter["type"]

    tags = _unique_tags(("external-memory", source, file_path.stem.lower(), *source_tags))
    return ExternalMemoryEntry(
        content=content,
        partition=partition,
        importance=importance,
        tags=tags,
        metadata=metadata,
        source_path=source_path,
    )


def _route_entry(
    source: ExternalSource,
    file_path: Path,
    source_path: str,
    frontmatter: dict[str, Any],
) -> tuple[str, float, tuple[str, ...]]:
    if source == "openhands":
        return PartitionType.PROCEDURAL.value, 6.0, _frontmatter_tags(frontmatter)

    if source == "openclaw":
        name = file_path.name.upper()
        if name == "USER.MD":
            return PartitionType.PREFERENCE.value, 7.0, ("user-profile",)
        if name == "SOUL.MD":
            return PartitionType.PROCEDURAL.value, 6.0, ("agent-identity",)
        if file_path.parent.name.lower() == "memory":
            return PartitionType.EPISODIC.value, 5.0, ("daily-memory",)
        return PartitionType.HIPPOCAMPUS.value, 7.0, ("long-term-memory",)

    memory_type = str(frontmatter.get("type") or "").strip().lower()
    category = str(frontmatter.get("category") or "").strip().lower()
    if any(token in category for token in _PROCEDURAL_CATEGORIES):
        partition = PartitionType.PROCEDURAL.value
    elif memory_type == "user":
        partition = PartitionType.PREFERENCE.value
    elif memory_type == "feedback":
        partition = PartitionType.EPISODIC.value
    elif memory_type in {"project", "reference"}:
        partition = PartitionType.SEMANTIC.value
    else:
        partition = PartitionType.HIPPOCAMPUS.value
    importance = _clamped_importance(frontmatter.get("importance"))
    return partition, importance, _unique_tags((*_frontmatter_tags(frontmatter), memory_type, category))


def _existing_external_keys(mind: HebbMind) -> set[str]:
    keys: set[str] = set()
    offset = 0
    page_size = 500
    while True:
        # Do not add a tag filter here. SQLite applies tag filtering after
        # LIMIT/OFFSET pagination, so filtering can miss older imported rows.
        memories, total = mind.list(offset=offset, limit=page_size)
        if not memories:
            break
        for memory in memories:
            value = (memory.metadata.model_extra or {}).get("external_key")
            if isinstance(value, str) and value:
                keys.add(value)
        offset += len(memories)
        if offset >= total:
            break
    return keys


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() != "---":
            continue
        values = _parse_frontmatter_lines(lines[1:index])
        return values, "".join(lines[index + 1 :]).lstrip("\r\n")
    return {}, text


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index].rstrip("\r\n")
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            index += 1
            continue

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value in {"|", ">"}:
            value, index = _parse_block_scalar(
                lines,
                start=index + 1,
                parent_indent=_line_indent(raw_line),
                folded=raw_value == ">",
            )
            values[key] = value
            continue
        if not raw_value:
            items, next_index = _parse_block_list(lines, start=index + 1)
            values[key] = items if items else ""
            index = next_index
            continue

        values[key] = _parse_frontmatter_value(raw_value)
        index += 1
    return values


def _parse_block_list(lines: list[str], *, start: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if not stripped.startswith("-"):
            break
        raw_item = stripped[1:].strip()
        if raw_item:
            items.append(_parse_frontmatter_value(raw_item))
        index += 1
    return items, index


def _parse_block_scalar(
    lines: list[str],
    *,
    start: int,
    parent_indent: int,
    folded: bool,
) -> tuple[str, int]:
    content: list[str] = []
    index = start
    while index < len(lines):
        raw_line = lines[index].rstrip("\r\n")
        if raw_line.strip() and _line_indent(raw_line) <= parent_indent:
            break
        content.append(raw_line.strip())
        index += 1
    separator = " " if folded else "\n"
    return separator.join(content).strip(), index


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _parse_frontmatter_value(raw: str) -> Any:
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_unquote(part.strip()) for part in inner.split(",") if part.strip()]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _unquote(raw)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _frontmatter_tags(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("tags", "triggers"):
        raw = frontmatter.get(field)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif isinstance(raw, str) and raw:
            values.append(raw)
    return _unique_tags(values)


def _unique_tags(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _clamped_importance(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 5.0
    return max(0.0, min(10.0, parsed))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _relative_source_path(file_path: Path, root: Path) -> str:
    if root.is_file():
        return file_path.name
    try:
        return file_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return file_path.name


__all__ = [
    "ExternalImportError",
    "ExternalMemoryEntry",
    "ExternalSource",
    "ImportSummary",
    "SUPPORTED_EXTERNAL_SOURCES",
    "discover_external_entries",
    "import_external_corpus",
]
