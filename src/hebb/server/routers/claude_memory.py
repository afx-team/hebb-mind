"""Claude Code file-based memory documents — discover, read, edit.

Surfaces the Markdown "auto memory" Claude Code keeps under
``~/.claude/projects/<slug>/memory/`` so the console can view and edit it
alongside Hebb Mind's own DB-backed memories. The heavy lifting (scanning,
path-traversal guards) lives in
:mod:`hebb.integrations.claude_code.memory_docs`; this router is a thin
HTTP layer over it.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from hebb.integrations.claude_code import memory_docs

router = APIRouter()


class MemoryProjectOut(BaseModel):
    slug: str
    path: str
    file_count: int
    has_index: bool
    updated_at: float


class MemoryFileOut(BaseModel):
    name: str
    size: int
    updated_at: float
    is_index: bool


class MemoryFileContent(BaseModel):
    project: str
    name: str
    content: str
    size: int
    updated_at: float


class MemoryFileUpdate(BaseModel):
    project: str
    name: str
    content: str


@router.get("/projects", response_model=list[MemoryProjectOut])
async def list_projects() -> list[MemoryProjectOut]:
    """List all Claude Code projects that have memory documents."""
    return [MemoryProjectOut(**asdict(p)) for p in memory_docs.list_projects()]


@router.get("/files", response_model=list[MemoryFileOut])
async def list_files(project: str = Query(...)) -> list[MemoryFileOut]:
    """List the memory documents in a single project."""
    try:
        return [MemoryFileOut(**asdict(f)) for f in memory_docs.list_files(project)]
    except memory_docs.UnsafePathError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/file", response_model=MemoryFileContent)
async def read_file(
    project: str = Query(...),
    name: str = Query(...),
) -> MemoryFileContent:
    """Return the raw content of one memory document."""
    try:
        content, st = memory_docs.read_file(project, name)
    except memory_docs.UnsafePathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Memory file not found")
    return MemoryFileContent(
        project=project,
        name=name,
        content=content,
        size=st.st_size,
        updated_at=st.st_mtime,
    )


@router.put("/file", response_model=MemoryFileContent)
async def write_file(req: MemoryFileUpdate) -> MemoryFileContent:
    """Overwrite an existing memory document with new content."""
    try:
        st = memory_docs.write_file(req.project, req.name, req.content)
    except memory_docs.UnsafePathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Memory file not found")
    return MemoryFileContent(
        project=req.project,
        name=req.name,
        content=req.content,
        size=st.st_size,
        updated_at=st.st_mtime,
    )
