"""Per-partition forgetting overrides as config (hebb.json), not data.

Covers the loader writer ``update_forgetting_overrides`` and round-tripping the
``forgetting_overrides`` map through ``Settings`` / hebb.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from hebb.config.loader import create_default_config, load_settings, update_forgetting_overrides
from hebb.config.settings import PartitionForgettingOverride, Settings


def test_settings_default_overrides_empty() -> None:
    assert Settings().forgetting_overrides == {}


def test_overrides_round_trip_through_settings() -> None:
    s = Settings(forgetting_overrides={"mem_facts": PartitionForgettingOverride(half_life_days=720.0, enabled=True)})
    dumped = s.model_dump()
    assert dumped["forgetting_overrides"]["mem_facts"]["half_life_days"] == 720.0
    # Re-parse (as load_settings does) — nested model rehydrates.
    reparsed = Settings(**dumped)
    ov = reparsed.forgetting_overrides["mem_facts"]
    assert isinstance(ov, PartitionForgettingOverride)
    assert ov.half_life_days == 720.0
    assert ov.k_access is None  # unset → inherit
    assert ov.threshold is None


def test_update_forgetting_overrides_persists_atomically(tmp_path: Path) -> None:
    cfg = tmp_path / "hebb.json"
    create_default_config(cfg)

    path, validated = update_forgetting_overrides(
        {"mem_facts": {"half_life_days": 720.0, "k_access": None, "enabled": True}},
        config_path=cfg,
    )
    assert path == cfg
    assert validated["mem_facts"]["half_life_days"] == 720.0

    on_disk = json.loads(cfg.read_text())
    assert on_disk["forgetting_overrides"]["mem_facts"]["half_life_days"] == 720.0
    # Other config keys are preserved by the read-modify-write.
    assert "half_life_days" in on_disk

    # load_settings reconstructs the typed override from disk.
    loaded = load_settings(config_path=cfg)
    assert loaded.forgetting_overrides["mem_facts"].half_life_days == 720.0


def test_update_forgetting_overrides_clear(tmp_path: Path) -> None:
    cfg = tmp_path / "hebb.json"
    create_default_config(cfg)
    update_forgetting_overrides({"mem_facts": {"enabled": False}}, config_path=cfg)
    # Clearing → empty map removes the entry.
    _, validated = update_forgetting_overrides({}, config_path=cfg)
    assert validated == {}
    assert json.loads(cfg.read_text())["forgetting_overrides"] == {}
