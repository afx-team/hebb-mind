"""Tests for config loading."""

import json
import os
from pathlib import Path

import pytest

from hippocampus.config.loader import create_default_config, load_settings, SECRETS
from hippocampus.config.settings import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.db_path == "hippocampus.db"
        assert s.embedding_dim == 384
        assert s.port == 8321

    def test_custom_values(self):
        s = Settings(port=9000, llm_model="anthropic/claude-3")
        assert s.port == 9000
        assert s.llm_model == "anthropic/claude-3"


class TestConfigLoader:
    def test_load_from_json(self, tmp_path: Path):
        config = {"port": 9999, "host": "127.0.0.1", "db_path": "custom.db"}
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.port == 9999
        assert settings.host == "127.0.0.1"
        assert settings.db_path == "custom.db"

    def test_secrets_stripped_from_json(self, tmp_path: Path):
        config = {"port": 8321, "llm_api_key": "should-be-ignored"}
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.llm_api_key is None  # Secret stripped

    def test_env_override(self, tmp_path: Path, monkeypatch):
        config = {"port": 8000}
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps(config))

        monkeypatch.setenv("HIPPOCAMPUS_PORT", "7777")
        settings = load_settings(config_path)
        assert settings.port == 7777  # Env overrides JSON

    def test_env_secrets(self, monkeypatch):
        monkeypatch.setenv("HIPPOCAMPUS_LLM_API_KEY", "my-secret-key")
        settings = load_settings(Path("/nonexistent/path"))
        assert settings.llm_api_key == "my-secret-key"

    def test_create_default_config(self, tmp_path: Path):
        target = tmp_path / "hippocampus.json"
        create_default_config(target)
        assert target.exists()
        data = json.loads(target.read_text())
        # Secrets should not be in the file
        for secret in SECRETS:
            assert secret not in data
        assert "port" in data
