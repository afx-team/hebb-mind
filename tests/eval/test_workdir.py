"""Unit tests for per-benchmark workdir + port allocation.

Verifies that each benchmark's hebb.json is provisioned in its own
subdir, inherits the project root's embedding settings, and overrides
host/port to the slot reserved in BENCHMARK_PORTS.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.client import BENCHMARK_PORTS, prepare_workdir


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Mimic the real repo root: a hebb.json with embedding settings."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "hebb.json").write_text(json.dumps({
        "home": None,
        "storage_type": "sqlite",
        "embedding_enabled": True,
        "embedding_provider": "local",
        "embedding_model": "BAAI/bge-large-en-v1.5",
        "embedding_dim": 1024,
        "hf_endpoint": None,
        "host": "127.0.0.1",
        "port": 9999,
        "weight_recency": 1.0,
        "weight_importance": 1.0,
        "weight_relevance": 1.0,
    }))
    return root


def test_prepare_workdir_creates_dir_and_writes_hebb_json(
    tmp_path: Path, project_root: Path
) -> None:
    workdir_root = tmp_path / "workdirs"

    workdir, port = prepare_workdir("convomem", workdir_root, project_root)

    # Defaults to mode="raw", appended as a suffix so the consolidated
    # workdir can persist independently.
    assert workdir == workdir_root / "convomem-raw"
    assert workdir.is_dir()
    assert port == BENCHMARK_PORTS["convomem"] == 8403

    cfg = json.loads((workdir / "hebb.json").read_text())
    # Inherited from project root
    assert cfg["embedding_model"] == "BAAI/bge-large-en-v1.5"
    assert cfg["embedding_dim"] == 1024
    assert cfg["embedding_provider"] == "local"
    assert cfg["storage_type"] == "sqlite"
    # Overridden
    assert cfg["host"] == "0.0.0.0"
    assert cfg["port"] == 8403
    # Reset so HEBB_HOME env wins
    assert cfg["home"] is None


def test_prepare_workdir_assigns_distinct_ports_per_benchmark(
    tmp_path: Path, project_root: Path
) -> None:
    workdir_root = tmp_path / "workdirs"

    ports = {
        name: prepare_workdir(name, workdir_root, project_root)[1]
        for name in ("locomo", "longmemeval", "convomem", "membench")
    }
    # No collisions
    assert len(set(ports.values())) == len(ports)
    # Each benchmark got its own dir (raw mode by default)
    for name in ports:
        assert (workdir_root / f"{name}-raw" / "hebb.json").exists()


def test_prepare_workdir_separates_modes(
    tmp_path: Path, project_root: Path
) -> None:
    """raw and consolidated must land in different subdirs so the
    persisted consolidated db isn't shadowed by a raw wipe."""
    workdir_root = tmp_path / "workdirs"

    wd_raw, port_raw = prepare_workdir(
        "convomem", workdir_root, project_root, mode="raw"
    )
    wd_cons, port_cons = prepare_workdir(
        "convomem", workdir_root, project_root, mode="consolidated"
    )

    assert wd_raw == workdir_root / "convomem-raw"
    assert wd_cons == workdir_root / "convomem-consolidated"
    assert wd_raw != wd_cons
    # Same benchmark → same port (sequential by design)
    assert port_raw == port_cons == BENCHMARK_PORTS["convomem"]


def test_prepare_workdir_rejects_unknown_benchmark(
    tmp_path: Path, project_root: Path
) -> None:
    with pytest.raises(ValueError, match="No port allocated"):
        prepare_workdir("not-a-real-benchmark", tmp_path / "wd", project_root)


def test_prepare_workdir_is_idempotent_and_refreshes_hebb_json(
    tmp_path: Path, project_root: Path
) -> None:
    """Re-running rewrites hebb.json so embedding changes propagate."""
    workdir_root = tmp_path / "workdirs"
    workdir, _ = prepare_workdir("membench", workdir_root, project_root)

    # User changes the project-root hebb.json (e.g. swapped embedding)
    cfg = json.loads((project_root / "hebb.json").read_text())
    cfg["embedding_model"] = "BAAI/bge-base-en-v1.5"
    cfg["embedding_dim"] = 768
    (project_root / "hebb.json").write_text(json.dumps(cfg))

    workdir2, _ = prepare_workdir("membench", workdir_root, project_root)
    assert workdir == workdir2
    new_cfg = json.loads((workdir / "hebb.json").read_text())
    assert new_cfg["embedding_model"] == "BAAI/bge-base-en-v1.5"
    assert new_cfg["embedding_dim"] == 768
    # Port is unchanged
    assert new_cfg["port"] == BENCHMARK_PORTS["membench"]


def test_prepare_workdir_handles_missing_project_hebb_json(
    tmp_path: Path
) -> None:
    """If the project has no hebb.json, the workdir still gets a minimal one."""
    project_root = tmp_path / "empty_project"
    project_root.mkdir()
    workdir_root = tmp_path / "wd"

    workdir, port = prepare_workdir("locomo", workdir_root, project_root)
    cfg = json.loads((workdir / "hebb.json").read_text())
    # Only host/port/home are set; everything else inherited (which is
    # nothing here) — server will fall back to its own defaults.
    assert cfg["host"] == "0.0.0.0"
    assert cfg["port"] == port
    assert cfg["home"] is None
