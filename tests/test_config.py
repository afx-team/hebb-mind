"""Tests for config loading."""

import json
from pathlib import Path

from hebb.config.loader import create_default_config, find_config_file, load_settings, update_config_field
from hebb.config.settings import Settings
from hebb.config.workspace import get_default_home, resolve_workspace


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.db_path == "hebb.db"
        assert s.kg_path == "knowledge_graph.json"
        assert s.embedding_dim == 384
        assert s.port == 8321
        assert s.embedding_provider == "local"
        assert s.embedding_api_key is None
        assert s.embedding_base_url is None
        assert s.home is None
        assert s.consolidation_time == "18:00"

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

    def test_db_path_derived_from_home_dir(self, tmp_path: Path):
        s = Settings(home_dir=tmp_path)
        assert s.db_path == str(tmp_path / "hebb.db")
        assert s.kg_path == str(tmp_path / "knowledge_graph.json")

    def test_db_path_fallback_without_home_dir(self):
        s = Settings()
        assert s.db_path == "hebb.db"
        assert s.kg_path == "knowledge_graph.json"

    def test_home_dir_not_in_model_dump(self):
        s = Settings()
        data = s.model_dump()
        assert "home_dir" not in data

    def test_db_path_kg_path_not_in_model_dump(self):
        """db_path and kg_path are computed properties, not persisted."""
        s = Settings()
        data = s.model_dump()
        assert "db_path" not in data
        assert "kg_path" not in data


class TestConfigLoader:
    def test_load_from_json(self, tmp_path: Path):
        config = {"port": 9999, "host": "127.0.0.1"}
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.port == 9999
        assert settings.host == "127.0.0.1"
        # db_path and kg_path are derived from home_dir (workspace)
        assert settings.db_path == str(tmp_path / "hebb.db")
        assert settings.kg_path == str(tmp_path / "knowledge_graph.json")
        assert settings.home_dir == tmp_path.resolve()

    def test_json_includes_all_fields(self, tmp_path: Path):
        config = {"port": 8321, "llm_api_key": "sk-test-key"}
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.llm_api_key == "sk-test-key"

    def test_create_default_config(self, tmp_path: Path):
        target = tmp_path / "hebb.json"
        create_default_config(target)
        assert target.exists()
        data = json.loads(target.read_text())
        assert "port" in data
        assert "embedding_provider" in data
        assert data["embedding_provider"] == "local"
        # db_path and kg_path should not be in the default config
        assert "db_path" not in data
        assert "kg_path" not in data

    def test_update_config_field(self, tmp_path: Path):
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"port": 8321}))

        update_config_field("port", "9000", config_path)
        data = json.loads(config_path.read_text())
        assert data["port"] == 9000

    def test_update_config_bool(self, tmp_path: Path):
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"embedding_enabled": True}))

        update_config_field("embedding_enabled", "false", config_path)
        data = json.loads(config_path.read_text())
        assert data["embedding_enabled"] is False

    def test_update_config_validates_consolidation_time(self, tmp_path: Path):
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"consolidation_time": "18:00"}))

        update_config_field("consolidation_time", "9:05", config_path)
        data = json.loads(config_path.read_text())
        assert data["consolidation_time"] == "09:05"

    def test_update_config_rejects_invalid_consolidation_time(self, tmp_path: Path):
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"consolidation_time": "18:00"}))

        try:
            update_config_field("consolidation_time", "25:00", config_path)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid consolidation_time should raise ValueError")

        data = json.loads(config_path.read_text())
        assert data["consolidation_time"] == "18:00"

    def test_home_field_in_config(self, tmp_path: Path):
        config = {"home": str(tmp_path / "custom_workspace")}
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        assert settings.home == str(tmp_path / "custom_workspace")
        # home_dir is resolved from the "home" field
        assert settings.home_dir == (tmp_path / "custom_workspace").resolve()
        assert settings.db_path == str((tmp_path / "custom_workspace").resolve() / "hebb.db")

    def test_home_field_relative_path(self, tmp_path: Path):
        config = {"home": "workspace_subdir"}
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps(config))

        settings = load_settings(config_path)
        # Relative "home" resolves against config file's parent
        assert settings.home_dir == (tmp_path / "workspace_subdir").resolve()

    def test_find_config_file_uses_hebb_home(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        config_path = home / "hebb.json"
        config_path.write_text("{}")
        monkeypatch.setenv("HEBB_HOME", str(home))

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        assert find_config_file(empty_dir) == config_path

    def test_find_config_file_does_not_fall_back_when_hebb_home_is_set(self, tmp_path: Path, monkeypatch):
        default_home = tmp_path / ".hebb"
        default_home.mkdir()
        (default_home / "hebb.json").write_text("{}")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("HEBB_HOME", str(tmp_path / "empty_home"))

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        assert find_config_file(empty_dir) is None

    def test_find_config_file_uses_default_home(self, tmp_path: Path, monkeypatch):
        default_home = tmp_path / ".hebb"
        default_home.mkdir()
        config_path = default_home / "hebb.json"
        config_path.write_text("{}")
        monkeypatch.delenv("HEBB_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        assert find_config_file(empty_dir) == config_path


class TestWorkspace:
    def test_default_home(self):
        home = get_default_home()
        assert home == Path.home() / ".hebb"

    def test_resolve_workspace_with_config_file(self, tmp_path: Path):
        config_path = tmp_path / "hebb.json"
        config_path.write_text("{}")

        workspace = resolve_workspace(config_path)
        assert workspace == tmp_path.resolve()

    def test_resolve_workspace_with_home_field(self, tmp_path: Path):
        custom = tmp_path / "custom_home"
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"home": str(custom)}))

        workspace = resolve_workspace(config_path)
        assert workspace == custom.resolve()
        assert custom.exists()  # auto-created

    def test_resolve_workspace_with_env_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HEBB_HOME", str(tmp_path))

        workspace = resolve_workspace()
        assert workspace == tmp_path.resolve()

    def test_resolve_workspace_env_creates_dir(self, tmp_path: Path, monkeypatch):
        new_dir = tmp_path / "new_home"
        assert not new_dir.exists()
        monkeypatch.setenv("HEBB_HOME", str(new_dir))

        workspace = resolve_workspace()
        assert workspace == new_dir.resolve()
        assert new_dir.exists()

    def test_resolve_workspace_env_overrides_home_field(self, tmp_path: Path, monkeypatch):
        env_dir = tmp_path / "env_home"
        config_dir = tmp_path / "config_home"
        config_path = tmp_path / "hebb.json"
        config_path.write_text(json.dumps({"home": str(config_dir)}))

        monkeypatch.setenv("HEBB_HOME", str(env_dir))
        workspace = resolve_workspace(config_path)
        # HEBB_HOME takes priority over "home" in config
        assert workspace == env_dir.resolve()
