"""Tests for the new MCP client installers (Gemini CLI, Goose, opencode, Amp).

Pattern follows test_codex_cli.py: monkeypatch paths and hebb_mcp_command,
invoke via Click's CliRunner, assert on generated config file content.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from hebb.integrations.amp.cli import amp
from hebb.integrations.gemini_cli.cli import gemini
from hebb.integrations.goose.cli import goose
from hebb.integrations.opencode.cli import opencode

# ── Gemini CLI ──────────────────────────────────────────────────────────


def test_gemini_install_creates_mcp_entry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.config_path",
        lambda: tmp_path / "settings.json",
    )
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(gemini, ["install"])

    assert result.exit_code == 0, result.output
    cfg = json.loads((tmp_path / "settings.json").read_text())
    assert cfg["mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"


def test_gemini_install_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.config_path",
        lambda: tmp_path / "settings.json",
    )
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    CliRunner().invoke(gemini, ["install"])
    result = CliRunner().invoke(gemini, ["install"])

    assert result.exit_code == 0, result.output
    cfg = json.loads((tmp_path / "settings.json").read_text())
    assert cfg["mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"


def test_gemini_install_preserves_existing(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"mcpServers": {"other": {"command": "/bin/other"}}, "theme": "dark"}))
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.config_path",
        lambda: settings,
    )
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(gemini, ["install"])

    assert result.exit_code == 0, result.output
    cfg = json.loads(settings.read_text())
    assert cfg["mcpServers"]["other"]["command"] == "/bin/other"
    assert cfg["mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"
    assert cfg["theme"] == "dark"


def test_gemini_uninstall_removes_entry(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"mcpServers": {"hebb": {"command": "/bin/hebb-mcp"}}}))
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.config_path",
        lambda: settings,
    )
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.uninstall.config_path",
        lambda: settings,
    )

    result = CliRunner().invoke(gemini, ["uninstall"])

    assert result.exit_code == 0, result.output
    cfg = json.loads(settings.read_text())
    assert "hebb" not in cfg.get("mcpServers", {})


def test_gemini_uninstall_when_absent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.install.config_path",
        lambda: tmp_path / "settings.json",
    )
    monkeypatch.setattr(
        "hebb.integrations.gemini_cli.uninstall.config_path",
        lambda: tmp_path / "settings.json",
    )

    result = CliRunner().invoke(gemini, ["uninstall"])

    assert result.exit_code == 0, result.output
    assert "not configured" in result.output.lower()


# ── opencode ────────────────────────────────────────────────────────────


def test_opencode_install_user_scope(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    monkeypatch.setattr(
        "hebb.integrations.opencode.install.config_path",
        lambda scope: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.opencode.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(opencode, ["install"])

    assert result.exit_code == 0, result.output
    data = json.loads(cfg.read_text())
    assert data["mcp"]["hebb"]["type"] == "local"
    assert data["mcp"]["hebb"]["command"] == ["/bin/hebb-mcp"]
    assert data["mcp"]["hebb"]["enabled"] is True


def test_opencode_install_preserves_existing(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"mcp": {"other": {"type": "remote", "url": "http://x"}}, "model": "test"}))
    monkeypatch.setattr(
        "hebb.integrations.opencode.install.config_path",
        lambda scope: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.opencode.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(opencode, ["install"])

    assert result.exit_code == 0, result.output
    data = json.loads(cfg.read_text())
    assert data["mcp"]["other"]["url"] == "http://x"
    assert data["mcp"]["hebb"]["command"] == ["/bin/hebb-mcp"]
    assert data["model"] == "test"


def test_opencode_uninstall(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"mcp": {"hebb": {"command": ["/bin/hebb-mcp"]}}}))
    monkeypatch.setattr(
        "hebb.integrations.opencode.install.config_path",
        lambda scope: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.opencode.uninstall.config_path",
        lambda scope: cfg,
    )

    result = CliRunner().invoke(opencode, ["uninstall"])

    assert result.exit_code == 0, result.output
    data = json.loads(cfg.read_text())
    assert "hebb" not in data.get("mcp", {})


# ── Amp ─────────────────────────────────────────────────────────────────


def test_amp_install_user_scope(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    monkeypatch.setattr(
        "hebb.integrations.amp.install.config_path",
        lambda scope: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.amp.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(amp, ["install"])

    assert result.exit_code == 0, result.output
    data = json.loads(cfg.read_text())
    assert data["amp.mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"


def test_amp_install_project_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "hebb.integrations.amp.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(amp, ["install", "--scope", "project"])

    assert result.exit_code == 0, result.output
    cfg = tmp_path / ".amp" / "settings.json"
    data = json.loads(cfg.read_text())
    assert data["amp.mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"


def test_amp_uninstall(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"amp.mcpServers": {"hebb": {"command": "/bin/hebb-mcp"}}}))
    monkeypatch.setattr(
        "hebb.integrations.amp.install.config_path",
        lambda scope: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.amp.uninstall.config_path",
        lambda scope: cfg,
    )

    result = CliRunner().invoke(amp, ["uninstall"])

    assert result.exit_code == 0, result.output
    data = json.loads(cfg.read_text())
    assert "hebb" not in data.get("amp.mcpServers", {})


# ── Goose (YAML) ────────────────────────────────────────────────────────


def test_goose_install_creates_extension(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(
        "hebb.integrations.goose.install.config_path",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.goose.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    result = CliRunner().invoke(goose, ["install"])

    assert result.exit_code == 0, result.output
    content = cfg.read_text()
    assert "hebb:" in content
    assert "type: stdio" in content
    assert "/bin/hebb-mcp" in content
    assert "enabled: true" in content


def test_goose_install_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(
        "hebb.integrations.goose.install.config_path",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.goose.install.hebb_mcp_command",
        lambda: ["/bin/hebb-mcp"],
    )

    CliRunner().invoke(goose, ["install"])
    result = CliRunner().invoke(goose, ["install"])

    assert result.exit_code == 0, result.output
    assert cfg.read_text().count("hebb:") == 1  # no duplicate blocks


def test_goose_uninstall(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "extensions:\n"
        "  hebb:\n"
        "    type: stdio\n"
        "    cmd: /bin/hebb-mcp\n"
        "    enabled: true\n"
    )
    monkeypatch.setattr(
        "hebb.integrations.goose.install.config_path",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "hebb.integrations.goose.uninstall.config_path",
        lambda: cfg,
    )

    result = CliRunner().invoke(goose, ["uninstall"])

    assert result.exit_code == 0, result.output
    content = cfg.read_text()
    assert "hebb" not in content
