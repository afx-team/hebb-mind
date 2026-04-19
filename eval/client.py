"""Async HTTP client for the hippocampus API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Server lifecycle management
# ------------------------------------------------------------------


def _find_pids_on_port(port: int) -> list[int]:
    """Find PIDs listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return []


def _read_hippocampus_config(project_root: Path | None = None) -> dict:
    """Read hippocampus.json from project root."""
    root = project_root or Path.cwd()
    cfg_path = root / "hippocampus.json"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return json.load(f)
    return {}


def stop_server(port: int) -> bool:
    """Stop any hippocampus server on the given port. Returns True if stopped."""
    pids = _find_pids_on_port(port)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(2)
    # Force kill any survivors
    remaining = _find_pids_on_port(port)
    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    if remaining:
        time.sleep(1)
    logger.info("Stopped server PIDs: %s", pids)
    return True


def clean_storage(project_root: Path | None = None) -> list[str]:
    """Delete db and knowledge_graph files for a clean environment.

    Returns list of deleted file paths.
    """
    root = project_root or Path.cwd()
    cfg = _read_hippocampus_config(root)

    db_path = root / cfg.get("db_path", "hippocampus.db")
    kg_path = root / cfg.get("kg_path", "knowledge_graph.json")

    deleted = []
    for p in [db_path, kg_path]:
        if p.exists():
            p.unlink()
            deleted.append(str(p))
        # Also remove WAL/SHM files for SQLite
        for suffix in ["-wal", "-shm"]:
            wal = p.parent / (p.name + suffix)
            if wal.exists():
                wal.unlink()
                deleted.append(str(wal))
    logger.info("Cleaned storage files: %s", deleted)
    return deleted


def _find_python(project_root: Path) -> str:
    """Find the best Python interpreter — prefer project venv."""
    venv_python = project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python"


def start_server(project_root: Path | None = None) -> subprocess.Popen:
    """Start hippocampus server as a background subprocess.

    Returns the Popen handle.
    """
    root = project_root or Path.cwd()
    cfg = _read_hippocampus_config(root)
    host = cfg.get("host", "0.0.0.0")
    port = cfg.get("port", 8321)
    python = _find_python(root)

    env = os.environ.copy()
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"

    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "hippocampus.server.app:app",
         "--host", host, "--port", str(port)],
        cwd=str(root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    logger.info("Started server PID %d on %s:%d", proc.pid, host, port)
    return proc


async def wait_for_server(base_url: str, timeout: float = 120.0) -> None:
    """Poll /health and /api/v1/admin/stats until the server is fully ready."""
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
        health_ok = False
        while time.monotonic() < deadline:
            try:
                if not health_ok:
                    r = await c.get(f"{base_url}/health")
                    if r.status_code == 200:
                        health_ok = True
                        logger.info("Health OK, waiting for full initialization...")
                else:
                    # Verify embedding + storage is ready via stats
                    r = await c.get(f"{base_url}/api/v1/admin/stats")
                    if r.status_code == 200:
                        logger.info("Server fully ready at %s", base_url)
                        return
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
                pass
            await asyncio.sleep(1.0)
    raise TimeoutError(f"Server not ready at {base_url} after {timeout}s")


class HippocampusClient:
    """Async HTTP client wrapping every hippocampus API endpoint."""

    def __init__(self, base_url: str = "http://localhost:8321", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        # trust_env=False bypasses system proxy — server is always local
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout, trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HippocampusClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        r = await self._client.get("/health")
        r.raise_for_status()
        return r.json()

    async def get_stats(self, timeout: float = 30.0) -> dict:
        r = await self._client.get("/api/v1/admin/stats", timeout=timeout)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Partitions
    # ------------------------------------------------------------------

    async def create_partition(
        self, partition_id: str, name: str, description: str = ""
    ) -> dict:
        r = await self._client.post(
            "/api/v1/partitions",
            json={"id": partition_id, "name": name, "description": description},
        )
        r.raise_for_status()
        return r.json()

    async def list_partitions(self) -> list[dict]:
        r = await self._client.get("/api/v1/partitions")
        r.raise_for_status()
        return r.json()

    async def delete_partition(self, partition_id: str) -> None:
        r = await self._client.delete(f"/api/v1/partitions/{partition_id}")
        r.raise_for_status()

    # ------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------

    async def create_memory(
        self,
        content: str,
        partition_id: str = "mem_hippocampus",
        importance_score: float = 5.0,
        tags: list[str] | None = None,
        metadata: dict[str, str] | None = None,
        source: str | None = None,
    ) -> dict:
        body: dict = {
            "content": content,
            "partition_id": partition_id,
            "importance_score": importance_score,
        }
        if tags:
            body["tags"] = tags
        if metadata:
            body["metadata"] = metadata
        if source:
            body["source"] = source
        r = await self._client.post("/api/v1/memories", json=body)
        r.raise_for_status()
        return r.json()

    async def create_memories_batch(self, items: list[dict]) -> list[dict]:
        r = await self._client.post("/api/v1/memories/batch", json=items)
        r.raise_for_status()
        return r.json()

    async def list_memories(
        self,
        partition_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        params: dict = {"offset": offset, "limit": limit}
        if partition_id:
            params["partition_id"] = partition_id
        r = await self._client.get("/api/v1/memories", params=params)
        r.raise_for_status()
        return r.json()

    async def delete_memory(self, memory_id: str) -> None:
        r = await self._client.delete(f"/api/v1/memories/{memory_id}")
        r.raise_for_status()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        partition_ids: list[str] | None = None,
        tags: list[str] | None = None,
        top_k: int = 10,
        weight_recency: float = 1.0,
        weight_importance: float = 1.0,
        weight_relevance: float = 1.0,
    ) -> list[dict]:
        body: dict = {
            "query": query,
            "top_k": top_k,
            "weight_recency": weight_recency,
            "weight_importance": weight_importance,
            "weight_relevance": weight_relevance,
        }
        if partition_ids:
            body["partition_ids"] = partition_ids
        if tags:
            body["tags"] = tags
        r = await self._client.post("/api/v1/search", json=body)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    async def trigger_consolidation(self) -> dict:
        """Trigger consolidation with a very long timeout.

        Consolidation processes all memories synchronously, which can take a long time.
        We use a 4-hour timeout to accommodate large datasets.
        """
        r = await self._client.post(
            "/api/v1/admin/consolidate",
            timeout=httpx.Timeout(connect=30.0, read=14400.0, write=30.0, pool=30.0),
        )
        r.raise_for_status()
        return r.json()

    async def trigger_forget(self) -> dict:
        r = await self._client.post("/api/v1/admin/forget")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    async def cleanup_partition(self, partition_id: str) -> int:
        """Delete all memories in a partition, then delete the partition.

        Returns the number of memories deleted.
        """
        deleted = 0
        while True:
            page = await self.list_memories(partition_id=partition_id, limit=50)
            items = page.get("items", [])
            if not items:
                break
            for mem in items:
                await self.delete_memory(mem["id"])
                deleted += 1
        try:
            await self.delete_partition(partition_id)
        except httpx.HTTPStatusError:
            pass  # partition may not exist or be a system partition
        return deleted
