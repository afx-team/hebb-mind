"""Configuration endpoints — read and update hebb.json."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from hebb.config.loader import load_settings, update_config_field
from hebb.config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Fixed mask returned by GET /config for any non-empty secret. Using a constant
# sentinel — rather than a length-dependent 4-char prefix/suffix reveal — means
# the masked value leaks nothing about the real secret (not even its length),
# and gives the test endpoints an unambiguous "this is masked" check instead of
# the fragile '****'-substring heuristic.
MASKED_PLACEHOLDER = "__hebb_masked__"

# Config keys whose values are secrets / credentials. embedding_http_headers is
# a JSON blob that often carries an Authorization token, so it is masked like a
# key; pg_url embeds a password in its userinfo.
SENSITIVE_KEYS = ("llm_api_key", "pg_url", "embedding_api_key", "embedding_http_headers")


def _is_masked(value: str | None) -> bool:
    """Return True if a client-supplied secret is the masking sentinel.

    Args:
        value: A secret value as received from the client (may be None).

    Returns:
        True when ``value`` equals :data:`MASKED_PLACEHOLDER`, meaning the
        client echoed back a masked field and the real stored value should be
        used instead.
    """
    return value == MASKED_PLACEHOLDER


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
    # Explicit opt-in required to change restart-required / infrastructure keys
    # (host, port, home, storage_type, pg_url). Console edits of editable keys
    # leave this False; an operator changing a guarded key must pass confirm.
    confirm: bool = False


# Keys the console may edit without an explicit confirm flag. Excludes the
# infrastructure / network-binding keys whose change has security or
# data-location consequences (host/port exposure, workspace relocation, storage
# backend, DB URL) — those require ConfigUpdateRequest.confirm=True. Also excludes
# ``forgetting_overrides``, a structured nested map edited through its own
# /api/v1/admin/forgetting router (the scalar key/value PUT cannot represent it).
CONSOLE_EDITABLE_KEYS = frozenset(Settings.model_fields.keys()) - frozenset(
    {"host", "port", "home", "storage_type", "pg_url", "home_dir", "forgetting_overrides"}
)

# Keys that may only be changed with an explicit confirm flag.
CONFIRM_REQUIRED_KEYS = frozenset({"host", "port", "home", "storage_type", "pg_url"})


@router.get("/config")
async def get_config() -> dict[str, Any]:
    """Return all current configuration values, secrets masked.

    Any non-empty secret is replaced with a fixed placeholder regardless of its
    length — the previous length-gated 4+4 prefix/suffix reveal leaked the first
    and last characters and the length of short keys.

    Returns:
        The config dict with :data:`SENSITIVE_KEYS` masked.
    """
    settings = load_settings()
    data = settings.model_dump()
    for key in SENSITIVE_KEYS:
        if data.get(key) and isinstance(data[key], str):
            data[key] = MASKED_PLACEHOLDER
    return data


@router.put("/config")
async def update_config(
    req: ConfigUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    """Update a single configuration field in hebb.json.

    The new value is also applied to the live ``app.state.settings`` so
    fields that don't require a restart (e.g. ``llm_*``) take effect on the
    next request. Restart-required fields update the file and the settings
    object, but the running services (storage, embedder, scheduler) keep
    their old instances until the server is restarted.
    """
    # Fields that require restart to take effect — the corresponding
    # service object was instantiated at lifespan startup with the old value.
    restart_fields = {
        "storage_type",
        "pg_url",
        "pg_pool_min",
        "pg_pool_max",
        "embedding_enabled",
        "embedding_provider",
        "embedding_model",
        "embedding_dim",
        "embedding_api_key",
        "embedding_base_url",
        "embedding_api_mode",
        "embedding_http_method",
        "embedding_http_url",
        "embedding_http_headers",
        "embedding_http_body",
        "embedding_http_response_path",
        "consolidation_time",
        "forget_interval_seconds",
        # Retrieval pipeline + rerank: the searcher and reranker are built
        # once at lifespan startup, so toggling these only takes effect after
        # a restart.
        "keyword_search_enabled",
        "graph_search_enabled",
        "lexical_boost_enabled",
        "temporal_boost_enabled",
        "graph_expansion_enabled",
        "rerank_enabled",
        "rerank_provider",
        "rerank_model",
        "rerank_top_n",
        "host",
        "port",
        "home",
    }

    # Allowlist enforcement: only known, console-editable keys are accepted.
    # Infrastructure / network-binding keys require an explicit confirm flag.
    if req.key not in Settings.model_fields or req.key == "home_dir":
        raise HTTPException(status_code=400, detail=f"Unknown or non-editable config key: {req.key!r}")
    if req.key in CONFIRM_REQUIRED_KEYS and not req.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{req.key!r} changes network binding, storage, or workspace location and requires "
                "confirm=true to apply."
            ),
        )
    if req.key not in CONSOLE_EDITABLE_KEYS and req.key not in CONFIRM_REQUIRED_KEYS:
        raise HTTPException(status_code=400, detail=f"Config key {req.key!r} is not editable via the API")

    # Validate workspace relocation before persisting: 'home' must be an existing
    # writable directory or we strand the daemon on a path it can't use.
    if req.key == "home" and req.value.lower() not in ("null", "none", ""):
        home_path = Path(req.value).expanduser()
        if not home_path.is_dir():
            raise HTTPException(status_code=400, detail=f"home must be an existing directory: {req.value}")
        if not os.access(home_path, os.W_OK):
            raise HTTPException(status_code=400, detail=f"home directory is not writable: {req.value}")

    try:
        _, coerced = update_config_field(req.key, req.value)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Config file not found")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Keep the live Settings instance in sync with the file so anything
    # holding a reference (router deps, SchedulerManager) sees the new value.
    settings: Settings = request.app.state.settings
    setattr(settings, req.key, coerced)

    return {
        "key": req.key,
        "value": req.value,
        "restart_required": req.key in restart_fields,
    }


@router.get("/config/reveal/{key}")
async def reveal_config_value(key: str) -> dict[str, Any]:
    """Return the unmasked value of a sensitive config field.

    Behind the anti-CSRF guard (INT-1): a cross-origin browser cannot reach this
    endpoint, so a malicious webpage can no longer exfiltrate the stored secret.

    Args:
        key: The sensitive config key to reveal.

    Returns:
        ``{"key": key, "value": <unmasked value>}``.

    Raises:
        HTTPException: 400 if ``key`` is not a sensitive field.
    """
    if key not in SENSITIVE_KEYS:
        raise HTTPException(status_code=400, detail="Only sensitive fields can be revealed")
    settings = load_settings()
    data = settings.model_dump()
    value = data.get(key)
    return {"key": key, "value": value}


class LLMTestRequest(BaseModel):
    model: str
    base_url: str | None = None
    api_key: str | None = None


@router.post("/config/test-llm")
async def test_llm_connection(req: LLMTestRequest) -> dict[str, Any]:
    """Test LLM connectivity with the provided credentials.

    Sends a minimal completion request to verify model/url/key work. When the
    caller echoes back the masking sentinel for ``api_key``, the real stored key
    is substituted — but ONLY if ``base_url`` matches the configured provider
    URL. If the caller points the test at a *different* URL while passing the
    masked key, the request is rejected: silently injecting the stored key into
    an arbitrary endpoint would exfiltrate it to an attacker-controlled URL.

    Args:
        req: Model, optional base_url, optional api_key (may be the sentinel).

    Returns:
        ``{"success": ..., ...}`` describing the connectivity probe.
    """
    # Catch common mistake: URL pasted into model field
    if req.model.startswith("http://") or req.model.startswith("https://"):
        return {
            "success": False,
            "error": (
                f"'{req.model}' looks like a URL, not a model name. "
                "The model field should be like 'openai/gpt-4o-mini' or 'openai/your-model'. "
                "Put the URL in the 'llm_base_url' field instead."
            ),
        }

    # If the key is masked (from GET /config), substitute the real stored key —
    # but only when the test targets the configured provider URL. Otherwise
    # require the caller to pass the key explicitly (anti-exfil / anti-SSRF).
    api_key = req.api_key
    if _is_masked(api_key):
        settings = load_settings()
        if req.base_url and req.base_url != settings.llm_base_url:
            return {
                "success": False,
                "error": (
                    "Refusing to send the stored API key to a different base_url. "
                    "Pass the api_key explicitly when testing against a non-configured URL."
                ),
            }
        api_key = settings.llm_api_key

    try:
        from litellm import acompletion

        kwargs: dict[str, Any] = {
            "model": req.model,
            "messages": [{"role": "user", "content": "Say 'ok' in one word."}],
            "temperature": 0,
            "max_tokens": 5,
        }
        if req.base_url:
            kwargs["api_base"] = req.base_url
        if api_key:
            kwargs["api_key"] = api_key

        response = await acompletion(**kwargs)
        content = response.choices[0].message.content or ""
        model_used = response.model or req.model
        return {"success": True, "response": content.strip(), "model": model_used}
    except Exception as e:
        return {"success": False, "error": str(e)}


class EmbeddingTestRequest(BaseModel):
    provider: Literal["local", "api"]
    model: str = ""
    base_url: str | None = None
    api_key: str | None = None
    # API transport — "litellm" (model + base_url) or "custom" (raw HTTP request).
    api_mode: Literal["litellm", "custom"] = "litellm"
    # Custom HTTP fields (only read when api_mode == "custom").
    http_method: str = "POST"
    http_url: str | None = None
    http_headers: str | None = None
    http_body: str | None = None
    http_response_path: str = "data.*.embedding"


async def _test_custom_http_embedding(req: EmbeddingTestRequest) -> dict[str, Any]:
    """Test a user-defined HTTP embedding request: one probe, report dimension."""
    from hebb.embedding.http_custom import CustomHttpEmbedder, parse_headers

    if not req.http_url:
        return {"success": False, "async": False, "error": "URL is required for custom HTTP embedding"}
    if not req.http_body:
        return {"success": False, "async": False, "error": "Request body is required for custom HTTP embedding"}

    # Headers may be masked (from GET /config) — substitute the stored value,
    # but only when the test targets the configured custom-embedding URL.
    # Sending the stored headers (which carry the bearer token) to a different
    # URL would exfiltrate the credential to an attacker-controlled endpoint.
    http_headers = req.http_headers
    if _is_masked(http_headers):
        settings = load_settings()
        if req.http_url and req.http_url != settings.embedding_http_url:
            return {
                "success": False,
                "async": False,
                "error": (
                    "Refusing to send the stored headers to a different URL. "
                    "Pass the headers explicitly when testing against a non-configured endpoint."
                ),
            }
        http_headers = settings.embedding_http_headers

    try:
        headers = parse_headers(http_headers)
        embedder = CustomHttpEmbedder(
            method=req.http_method or "POST",
            url=req.http_url,
            headers=headers,
            body_template=req.http_body,
            response_path=req.http_response_path or "data.*.embedding",
        )
        vec = await embedder.embed("embedding test")
    except Exception as e:
        return {"success": False, "async": False, "error": str(e)}

    return {
        "success": True,
        "async": False,
        "dimension": len(vec),
        "message": f"Endpoint responded, dimension={len(vec)}",
    }


@router.post("/config/test-embedding")
async def test_embedding(req: EmbeddingTestRequest) -> dict[str, Any]:
    """Test embedding connectivity — local model load or API call.

    Local + already cached, or any API request: sync response with dimension.
    Local + not cached: starts a background download and returns a ``task_id``
    the client polls via ``GET /config/test-embedding/status/{task_id}``.
    """
    if req.provider == "api" and req.api_mode == "custom":
        return await _test_custom_http_embedding(req)

    # Masked api_key → substitute the stored embedding key, but only when the
    # test targets the configured embedding base_url (anti-exfil / anti-SSRF).
    api_key = req.api_key
    if _is_masked(api_key):
        settings = load_settings()
        if req.base_url and req.base_url != settings.embedding_base_url:
            return {
                "success": False,
                "async": False,
                "error": (
                    "Refusing to send the stored API key to a different base_url. "
                    "Pass the api_key explicitly when testing against a non-configured URL."
                ),
            }
        api_key = settings.embedding_api_key

    if req.provider == "local":
        from hebb.embedding.local import LocalEmbedder, is_model_cached

        cached = is_model_cached(req.model)
        if cached:
            try:
                embedder = LocalEmbedder(req.model)
                vec = await embedder.embed("test")
                return {
                    "success": True,
                    "async": False,
                    "dimension": embedder.dimension,
                    "message": (
                        f"Model loaded from cache, dimension={embedder.dimension}, sample vector length={len(vec)}"
                    ),
                }
            except Exception:
                # A "cached" model that won't load usually means an interrupted
                # or corrupt download (config present, weights missing). Fall
                # through to re-download instead of dead-ending on the error.
                logger.warning(
                    "Cached local model %s failed to load; re-downloading to repair", req.model, exc_info=True
                )

        # Not cached (or the cached copy failed to load): start a background
        # download + verification.
        from hebb.config.workspace import resolve_workspace
        from hebb.embedding.catalog import prefetch_model
        from hebb.server.downloads import cleanup_old_tasks, create_task, update_task

        cleanup_old_tasks()
        settings = load_settings()
        hf_endpoint = settings.hf_endpoint
        try:
            workspace = resolve_workspace()
        except Exception as e:
            return {"success": False, "async": False, "error": f"Workspace not resolved: {e}"}

        task = create_task(req.model, "local")
        model_id = req.model

        def _progress(done: int, total: int, current: str) -> None:
            update_task(task.task_id, bytes_done=done, bytes_total=total, current_file=current)

        def _download() -> None:
            prefetch_model(model_id, workspace, hf_endpoint=hf_endpoint, progress_callback=_progress)

        async def _run() -> None:
            try:
                update_task(task.task_id, status="downloading")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _download)
                update_task(task.task_id, status="verifying")
                embedder = LocalEmbedder(model_id, hf_endpoint=hf_endpoint)
                await embedder.embed("test")
                update_task(task.task_id, status="done", dimension=embedder.dimension)
            except Exception as e:
                logger.exception("Embedding download task failed: %s", model_id)
                update_task(task.task_id, status="failed", error=str(e))

        asyncio.create_task(_run())
        return {
            "success": True,
            "async": True,
            "task_id": task.task_id,
            "message": f"Downloading {model_id} — poll for progress",
        }

    # API provider
    if not req.base_url:
        return {"success": False, "async": False, "error": "base_url is required for API embedding"}
    try:
        from litellm import aembedding

        kwargs: dict[str, Any] = {"model": req.model, "input": ["embedding test"]}
        if api_key:
            kwargs["api_key"] = api_key
        if req.base_url:
            kwargs["api_base"] = req.base_url
        response = await aembedding(**kwargs)
        dim = len(response.data[0]["embedding"])
        return {
            "success": True,
            "async": False,
            "dimension": dim,
            "message": f"API responded, dimension={dim}",
        }
    except Exception as e:
        return {"success": False, "async": False, "error": str(e)}


@router.get("/config/test-embedding/status/{task_id}")
async def test_embedding_status(task_id: str) -> dict[str, Any]:
    """Return progress for an async embedding-download task started by test_embedding."""
    from hebb.server.downloads import get_task

    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_id not found (may have been cleaned up)")
    return task.to_dict()


@router.get("/config/embedding-status")
async def embedding_status() -> dict[str, Any]:
    """Return current embedding model status: provider, model, cached, dimension."""
    settings = load_settings()
    result: dict[str, Any] = {
        "enabled": settings.embedding_enabled,
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
    }
    if not settings.embedding_enabled:
        result["status"] = "disabled"
    elif settings.embedding_provider == "api":
        result["status"] = "api"
        result["api_mode"] = settings.embedding_api_mode
        if settings.embedding_api_mode == "custom":
            result["url"] = settings.embedding_http_url or None
        else:
            result["base_url"] = settings.embedding_base_url or None
    else:
        from hebb.embedding.local import is_model_cached

        cached = is_model_cached(settings.embedding_model)
        result["status"] = "cached" if cached else "not_downloaded"
        result["cached"] = cached
    return result


@router.get("/config/fields")
async def get_config_fields() -> list[dict[str, Any]]:
    """Return metadata about all configuration fields."""
    fields: list[dict[str, Any]] = []
    for name, info in Settings.model_fields.items():
        annotation = info.annotation
        type_name = "string"
        if annotation is int:
            type_name = "number"
        elif annotation is float:
            type_name = "number"
        elif annotation is bool:
            type_name = "boolean"

        fields.append(
            {
                "key": name,
                "type": type_name,
                "description": info.description or "",
                "default": info.default,
            }
        )
    return fields
