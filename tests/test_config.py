"""Tests for config loading."""

import json
from pathlib import Path

from hippocampus.config.loader import create_default_config, load_settings, update_config_field
from hippocampus.config.settings import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.db_path == "hippocampus.db"
        assert s.embedding_dim == 384
        assert s.port == 8321
        assert s.embedding_provider == "local"
        assert s.embedding_api_key is None
        assert s.embedding_base_url is None

    def test_custom_values(self):
        s = Settings(port=9000, llm_model="anthropic/claude-3")
        assert s.port == 9000
        assert s.llm_model == "anthropic/claude-3"

    def test_embedding_api_config(self):
        s = Settings(
            embedding_provider="api",
            embedding_model="openai/text-embedding-3-small",
            embedding_api_key="sk-test",
            embedding_base_url="https://api.example.com",
        )
        assert s.embedding_provider == "api"
        assert s.embedding_model == "openai/text-embedding-3-small"
        assert s.embedding_api_key == "sk-test"


class TestConfigLoader:
    def test_load_from_json(self, tmp_path: Path):
        config = {"port": 9999, "host": "127.0.0.1", "db_path": "custom.db"}
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.port == 9999
        assert settings.host == "127.0.0.1"
        assert settings.db_path == "custom.db"

    def test_json_includes_all_fields(self, tmp_path: Path):
        config = {"port": 8321, "llm_api_key": "sk-test-key"}
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.llm_api_key == "sk-test-key"

    def test_create_default_config(self, tmp_path: Path):
        target = tmp_path / "hippocampus.json"
        create_default_config(target)
        assert target.exists()
        data = json.loads(target.read_text())
        assert "port" in data
        assert "embedding_provider" in data
        assert data["embedding_provider"] == "local"

    def test_update_config_field(self, tmp_path: Path):
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps({"port": 8321}))

        update_config_field("port", "9000", config_path)
        data = json.loads(config_path.read_text())
        assert data["port"] == 9000

    def test_update_config_bool(self, tmp_path: Path):
        config_path = tmp_path / "hippocampus.json"
        config_path.write_text(json.dumps({"embedding_enabled": True}))

        update_config_field("embedding_enabled", "false", config_path)
        data = json.loads(config_path.read_text())
        assert data["embedding_enabled"] is False
