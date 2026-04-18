"""Configuration endpoints — read and update hippocampus.json."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hippocampus.config.loader import find_config_file, load_settings, update_config_field
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
    for key in ("llm_api_key", "pg_url"):
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
        "storage_type", "db_path", "pg_url", "pg_pool_min", "pg_pool_max",
        "embedding_enabled", "embedding_model", "embedding_dim",
        "host", "port", "kg_path",
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
    if key not in ("llm_api_key", "pg_url"):
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

        fields.append({
            "key": name,
            "type": type_name,
            "description": info.description or "",
            "default": info.default,
        })
    return fields
