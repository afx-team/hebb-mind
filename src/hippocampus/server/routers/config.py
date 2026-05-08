"""Configuration endpoints — read and update hippocampus.json."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hippocampus.config.loader import load_settings, update_config_field
from hippocampus.config.settings import Settings

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


@router.get("/config")
async def get_config() -> dict:
    """Return all current configuration values."""
    settings = load_settings()
    data = settings.model_dump()
    # Mask sensitive values
    for key in ("llm_api_key", "pg_url", "embedding_api_key"):
        if data.get(key) and isinstance(data[key], str) and len(data[key]) > 8:
            data[key] = data[key][:4] + "****" + data[key][-4:]
    return data


@router.put("/config")
async def update_config(
    req: ConfigUpdateRequest,
) -> dict:
    """Update a single configuration field in hippocampus.json.

    Note: some changes (port, storage_type, embedding_model) require a server restart.
    """
    # Fields that require restart to take effect
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
        "host",
        "port",
        "home",
    }

    try:
        update_config_field(req.key, req.value)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Config file not found")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "key": req.key,
        "value": req.value,
        "restart_required": req.key in restart_fields,
    }


@router.get("/config/reveal/{key}")
async def reveal_config_value(key: str) -> dict:
    """Return the unmasked value of a sensitive config field."""
    if key not in ("llm_api_key", "pg_url", "embedding_api_key"):
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
async def test_llm_connection(req: LLMTestRequest) -> dict:
    """Test LLM connectivity with the provided credentials.

    Sends a minimal completion request to verify model/url/key work.
    If api_key contains '****' (masked), reads the real key from config file.
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

    # If the key is masked (from GET /config), read real key from config
    api_key = req.api_key
    if api_key and "****" in api_key:
        settings = load_settings()
        api_key = settings.llm_api_key

    try:
        from litellm import acompletion

        kwargs: dict = {
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
    provider: str  # "local" or "api"
    model: str
    base_url: str | None = None
    api_key: str | None = None


@router.post("/config/test-embedding")
async def test_embedding(req: EmbeddingTestRequest) -> dict:
    """Test embedding connectivity — local model load or API call.

    If api_key contains '****' (masked), reads the real key from config file.
    """
    api_key = req.api_key
    if api_key and "****" in api_key:
        settings = load_settings()
        api_key = settings.embedding_api_key

    if req.provider == "local":
        try:
            from hippocampus.embedding.local import LocalEmbedder

            embedder = LocalEmbedder(req.model)
            vec = await embedder.embed("test")
            return {
                "success": True,
                "dimension": embedder.dimension,
                "message": f"Model loaded, dimension={embedder.dimension}, sample vector length={len(vec)}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        if not req.base_url:
            return {"success": False, "error": "base_url is required for API embedding"}
        try:
            from litellm import aembedding

            kwargs: dict = {"model": req.model, "input": ["embedding test"]}
            if api_key:
                kwargs["api_key"] = api_key
            if req.base_url:
                kwargs["api_base"] = req.base_url
            response = await aembedding(**kwargs)
            dim = len(response.data[0]["embedding"])
            return {
                "success": True,
                "dimension": dim,
                "message": f"API responded, dimension={dim}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


@router.get("/config/embedding-status")
async def embedding_status() -> dict:
    """Return current embedding model status: provider, model, cached, dimension."""
    settings = load_settings()
    result: dict = {
        "enabled": settings.embedding_enabled,
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
    }
    if not settings.embedding_enabled:
        result["status"] = "disabled"
    elif settings.embedding_provider == "api":
        result["status"] = "api"
        result["base_url"] = settings.embedding_base_url or None
    else:
        from hippocampus.embedding.local import is_model_cached

        cached = is_model_cached(settings.embedding_model)
        result["status"] = "cached" if cached else "not_downloaded"
        result["cached"] = cached
    return result


@router.get("/config/fields")
async def get_config_fields() -> list[dict]:
    """Return metadata about all configuration fields."""
    fields = []
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
