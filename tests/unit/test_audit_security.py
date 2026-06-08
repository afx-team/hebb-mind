"""Audit lane B-security: secret masking, config-write allowlist, doctor gating, anti-CSRF.

Covers the fixes in:
    * ``hebb.server.routers.config`` — fixed-placeholder masking of any non-empty
      secret (no length gate / prefix-suffix leak), PUT /config allowlist +
      confirm flag, and the sentinel-based (not '****'-substring) masked-value
      detection plus the no-exfil-to-foreign-URL rule on the test endpoints.
    * ``hebb.cli.commands.config`` — CLI ``_mask`` covers embedding_http_headers
      and pg_url credentials, matching the server.
    * ``hebb.cli.commands.doctor`` — consolidation readiness gates on llm_model.
    * ``hebb.server.auth`` — cross-origin browser requests to guarded routes are
      rejected; same-origin and header-less (non-browser) requests pass.

Route handlers are exercised directly; the auth guard via its pure predicate +
its middleware over a tiny app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from rich.table import Table

from hebb.cli.commands import config as cli_config
from hebb.cli.commands import doctor as cli_doctor
from hebb.config.settings import Settings
from hebb.server import auth
from hebb.server.routers import config as config_router


# --------------------------------------------------------------------------- #
# GET /config masking: ANY non-empty secret -> fixed placeholder, no leak.
# --------------------------------------------------------------------------- #
class TestServerMasking:
    @pytest.mark.asyncio
    async def test_long_secret_fully_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        secret = "sk-abcdefgh12345678ijklmnop"
        monkeypatch.setattr(
            config_router,
            "load_settings",
            lambda *a, **k: Settings(llm_api_key=secret, pg_url="postgresql://u:pw@h/db"),
        )
        data = await config_router.get_config()
        assert data["llm_api_key"] == config_router.MASKED_PLACEHOLDER
        # No fragment of the real secret leaks (length, prefix, suffix).
        assert secret not in data["llm_api_key"]
        assert secret[:4] not in data["llm_api_key"]
        assert secret[-4:] not in data["llm_api_key"]

    @pytest.mark.asyncio
    async def test_short_secret_also_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The old len>8 gate left short keys fully visible — this is the bug.
        short = "sk-12"
        monkeypatch.setattr(config_router, "load_settings", lambda *a, **k: Settings(llm_api_key=short))
        data = await config_router.get_config()
        assert data["llm_api_key"] == config_router.MASKED_PLACEHOLDER
        assert short not in data["llm_api_key"]

    @pytest.mark.asyncio
    async def test_empty_secret_not_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config_router, "load_settings", lambda *a, **k: Settings(llm_api_key=None))
        data = await config_router.get_config()
        assert data["llm_api_key"] is None


# --------------------------------------------------------------------------- #
# PUT /config: allowlist + confirm flag for infrastructure keys.
# --------------------------------------------------------------------------- #
class _FakeAppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings


class _FakeApp:
    def __init__(self, settings: Settings) -> None:
        self.state = _FakeAppState(settings)


class _FakeRequest:
    def __init__(self, settings: Settings) -> None:
        self.app = _FakeApp(settings)


def _fake_request(settings: Settings) -> Any:
    """A duck-typed stand-in for starlette ``Request`` (only ``.app.state`` used)."""
    return _FakeRequest(settings)


def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "hebb.json"
    cfg.write_text(json.dumps(Settings().model_dump(exclude={"home_dir"})))
    return cfg


class TestConfigWriteAllowlist:
    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self) -> None:
        req = config_router.ConfigUpdateRequest(key="not_a_real_key", value="x")
        with pytest.raises(HTTPException) as exc:
            await config_router.update_config(req, _fake_request(Settings()))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_computed_home_dir_rejected(self) -> None:
        req = config_router.ConfigUpdateRequest(key="home_dir", value="/tmp")
        with pytest.raises(HTTPException) as exc:
            await config_router.update_config(req, _fake_request(Settings()))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_infrastructure_key_requires_confirm(self) -> None:
        req = config_router.ConfigUpdateRequest(key="host", value="0.0.0.0")
        with pytest.raises(HTTPException) as exc:
            await config_router.update_config(req, _fake_request(Settings()))
        assert exc.value.status_code == 400
        assert "confirm" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_editable_key_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _write_config(tmp_path)
        monkeypatch.setattr(config_router, "update_config_field", lambda k, v: (cfg, v))
        req = config_router.ConfigUpdateRequest(key="llm_model", value="openai/gpt-4o-mini")
        settings = Settings()
        result = await config_router.update_config(req, _fake_request(settings))
        assert result["key"] == "llm_model"
        assert settings.llm_model == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_home_must_be_existing_dir(self) -> None:
        req = config_router.ConfigUpdateRequest(key="home", value="/no/such/dir/here", confirm=True)
        with pytest.raises(HTTPException) as exc:
            await config_router.update_config(req, _fake_request(Settings()))
        assert exc.value.status_code == 400

    def test_console_editable_excludes_infra(self) -> None:
        for key in ("host", "port", "home", "storage_type", "pg_url", "home_dir"):
            assert key not in config_router.CONSOLE_EDITABLE_KEYS


# --------------------------------------------------------------------------- #
# Masked-value detection via sentinel, no '****' substring heuristic.
# --------------------------------------------------------------------------- #
class TestMaskedDetection:
    def test_sentinel_is_masked(self) -> None:
        assert config_router._is_masked(config_router.MASKED_PLACEHOLDER) is True

    def test_real_value_with_stars_not_masked(self) -> None:
        # A real key/header that happens to contain '****' must NOT be treated as
        # masked — the old substring heuristic mis-fired on such values.
        assert config_router._is_masked("Bearer ****real-token****") is False
        assert config_router._is_masked(None) is False

    @pytest.mark.asyncio
    async def test_test_llm_refuses_key_to_foreign_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            config_router,
            "load_settings",
            lambda *a, **k: Settings(llm_api_key="sk-secret", llm_base_url="https://configured.example"),
        )
        req = config_router.LLMTestRequest(
            model="openai/gpt-4o-mini",
            base_url="https://attacker.example",
            api_key=config_router.MASKED_PLACEHOLDER,
        )
        result = await config_router.test_llm_connection(req)
        assert result["success"] is False
        assert "stored api key" in result["error"].lower()


# --------------------------------------------------------------------------- #
# CLI _mask parity with the server.
# --------------------------------------------------------------------------- #
class TestCliMask:
    def test_embedding_http_headers_masked(self) -> None:
        out = cli_config._mask("embedding_http_headers", '{"Authorization": "Bearer sk-secret"}')
        assert "sk-secret" not in out
        assert out == "****"

    def test_pg_url_password_masked(self) -> None:
        out = cli_config._mask("pg_url", "postgresql://admin:supersecret@db.host:5432/hebb")
        assert "supersecret" not in out
        assert "admin" in out  # non-secret parts retained for diagnosis
        assert "db.host" in out

    def test_short_api_key_masked(self) -> None:
        # No length gate any more.
        out = cli_config._mask("llm_api_key", "sk-1")
        assert out == "****"

    def test_non_secret_unchanged(self) -> None:
        assert cli_config._mask("port", 8321) == "8321"


# --------------------------------------------------------------------------- #
# doctor gates consolidation readiness on llm_model.
# --------------------------------------------------------------------------- #
class TestDoctorLlmGate:
    def test_llm_model_set_is_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / "hebb.json"
        cfg.write_text(json.dumps({"llm_model": "openai/gpt-4o-mini"}))
        monkeypatch.setattr(cli_doctor, "find_config_file", lambda: cfg)
        table = Table()
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Details")
        cli_doctor._add_config_check(table)
        rows = _render_rows(table)
        llm = [r for r in rows if r[0] == "LLM"][0]
        assert llm[1] == "[OK]"
        assert "openai/gpt-4o-mini" in llm[2]

    def test_no_llm_model_warns_even_with_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / "hebb.json"
        # Key present but no model — must still WARN (the real gate is the model).
        cfg.write_text(json.dumps({"llm_api_key": "sk-secret"}))
        monkeypatch.setattr(cli_doctor, "find_config_file", lambda: cfg)
        table = Table()
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Details")
        cli_doctor._add_config_check(table)
        rows = _render_rows(table)
        llm = [r for r in rows if r[0] == "LLM"][0]
        assert llm[1] == "[WARN]"
        assert "llm_model" in llm[2]


def _render_rows(table: Table) -> list[tuple[str, str, str]]:
    """Extract (check, status, details) cell text from a rich Table."""
    cols = [list(c.cells) for c in table.columns]
    rows: list[tuple[str, str, str]] = []
    for i in range(len(cols[0])):
        rows.append((str(cols[0][i]), str(cols[1][i]), str(cols[2][i])))
    return rows


# --------------------------------------------------------------------------- #
# Anti-CSRF guard.
# --------------------------------------------------------------------------- #
class TestAntiCsrfPredicate:
    def test_state_changing_methods_guarded(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert auth._is_guarded(method, "/api/v1/memories") is True

    def test_safe_get_not_guarded(self) -> None:
        assert auth._is_guarded("GET", "/api/v1/memories") is False

    def test_reveal_get_guarded(self) -> None:
        assert auth._is_guarded("GET", "/api/v1/admin/config/reveal/llm_api_key") is True

    def test_config_test_guarded(self) -> None:
        assert auth._is_guarded("GET", "/api/v1/admin/config/test-embedding/status/abc") is True


class TestAntiCsrfMiddleware:
    def _app(self) -> Any:
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(auth.AntiCsrfMiddleware)
        app.state.settings = Settings(port=8321)

        @app.post("/api/v1/memories")
        async def _create() -> dict[str, str]:
            return {"ok": "1"}

        @app.get("/api/v1/memories")
        async def _list() -> dict[str, str]:
            return {"ok": "1"}

        return TestClient(app)

    def test_cross_origin_post_rejected(self) -> None:
        client = self._app()
        resp = client.post("/api/v1/memories", headers={"origin": "https://evil.example"})
        assert resp.status_code == 403

    def test_same_origin_post_allowed(self) -> None:
        client = self._app()
        resp = client.post("/api/v1/memories", headers={"origin": "http://127.0.0.1:8321"})
        assert resp.status_code == 200

    def test_no_origin_header_allowed(self) -> None:
        # Non-browser client (CLI / MCP) — no Origin header, must pass.
        client = self._app()
        resp = client.post("/api/v1/memories")
        assert resp.status_code == 200

    def test_cross_origin_safe_get_allowed(self) -> None:
        client = self._app()
        resp = client.get("/api/v1/memories", headers={"origin": "https://evil.example"})
        assert resp.status_code == 200
