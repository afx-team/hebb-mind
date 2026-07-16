"""Embedding model catalog, language selection, and download source selection."""

from __future__ import annotations

import locale
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from hebb.embedding.progress import ProgressCallback

HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
HF_OFFICIAL_ENDPOINT = "https://huggingface.co"

LANGUAGE_CHOICES = ("auto", "en", "zh", "multi")
REGION_CHOICES = ("auto", "cn", "global")
PROFILE_CHOICES = ("default", "fast", "best")

LEGACY_DEFAULT_MODELS = {
    "all-MiniLM-L6-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
}


@dataclass(frozen=True)
class ModelSpec:
    """Embedding model metadata."""

    model_id: str
    dimension: int
    language: str
    profile: str


@dataclass(frozen=True)
class LanguageSelection:
    """Resolved language selection."""

    language: str
    source: str
    raw: str | None = None


@dataclass(frozen=True)
class RegionSelection:
    """Resolved download region and HuggingFace endpoint."""

    region: str
    hf_endpoint: str | None
    source: str
    message: str | None = None


@dataclass(frozen=True)
class ProbeResult:
    """Network probe result for a download endpoint."""

    region: str
    endpoint: str
    available: bool
    latency_ms: float | None
    error: str | None = None


MODEL_DIMS: dict[str, int] = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-m3": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "all-MiniLM-L6-v2": 384,
    "intfloat/multilingual-e5-small": 384,
}

# Redundant weight variants we never load (PyTorch/safetensors is enough).
# Skipping these in ``snapshot_download`` roughly halves the bytes pulled for
# repos that ship ONNX/OpenVINO/TensorFlow exports alongside the torch weights.
# NOTE: keep ``*.bin`` and ``*.safetensors`` — ``model_dir_complete`` requires a
# real weight file (``model.safetensors`` OR ``pytorch_model.bin``). The helper
# below conditionally excludes the exact redundant .bin filename only for
# built-in repositories verified to publish safetensors.
PREFETCH_IGNORE_PATTERNS: tuple[str, ...] = (
    "*.onnx",
    "onnx/**",
    "openvino/**",
    "openvino_model.*",
    "*.h5",
    "tf_model.h5",
    "*.ckpt",
    "*.msgpack",
    "*.pb",
)

# These built-in models publish a safetensors checkpoint alongside redundant
# framework-specific copies. Prefer the safe format while retaining
# ``pytorch_model.bin`` for BGE-M3 and unknown/custom repositories that may not
# publish safetensors at all.
_SAFETENSORS_MODELS = frozenset(
    {
        "all-MiniLM-L6-v2",
        "sentence-transformers/all-MiniLM-L6-v2",
        "intfloat/multilingual-e5-small",
        "BAAI/bge-large-en-v1.5",
    }
)
_REDUNDANT_TORCH_WEIGHT_PATTERNS: tuple[str, ...] = (
    "pytorch_model.bin",
    "rust_model.ot",
)


def resolve_language(language: str = "auto", environ: dict[str, str] | None = None) -> LanguageSelection:
    """Resolve the content language strategy.

    Args:
        language: Explicit language value: auto, en, zh, or multi.
        environ: Optional environment mapping for tests.

    Returns:
        The resolved language and detection source.

    Raises:
        ValueError: If language is not one of the supported choices.
    """
    if language not in LANGUAGE_CHOICES:
        raise ValueError(f"Unsupported language: {language!r}")
    if language != "auto":
        return LanguageSelection(language=language, source="explicit")

    raw_locale = _detect_locale(dict(os.environ) if environ is None else environ)
    detected = _language_from_locale(raw_locale)
    return LanguageSelection(language=detected, source="locale", raw=raw_locale)


def choose_model(language: str, profile: str = "default") -> ModelSpec:
    """Choose the default embedding model for a language and profile.

    The ``default`` profile selects a *small* model so a bare ``hebb setup``
    never triggers a multi-gigabyte download. The high-quality ``bge`` models
    are the explicit ``best`` opt-in tier.

    Profile mapping:

    - ``fast``   -> ``all-MiniLM-L6-v2`` (~90MB, smallest).
    - ``best``   -> ``BAAI/bge-large-en-v1.5`` (en) / ``BAAI/bge-m3`` (zh, multi),
      the 1-2GB+ high-quality tier.
    - ``default`` -> ``all-MiniLM-L6-v2`` (en, ~90MB) /
      ``intfloat/multilingual-e5-small`` (zh, multi, ~470MB, multilingual).

    Args:
        language: Resolved language: en, zh, or multi.
        profile: Model profile: default, fast, or best.

    Returns:
        Model metadata containing model ID and vector dimension.

    Raises:
        ValueError: If language or profile is unsupported.
    """
    if language not in ("en", "zh", "multi"):
        raise ValueError(f"Unsupported resolved language: {language!r}")
    if profile not in PROFILE_CHOICES:
        raise ValueError(f"Unsupported profile: {profile!r}")

    if profile == "fast":
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
    elif profile == "best":
        model_id = "BAAI/bge-large-en-v1.5" if language == "en" else "BAAI/bge-m3"
    elif language == "en":
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
    else:
        model_id = "intfloat/multilingual-e5-small"

    return ModelSpec(
        model_id=model_id,
        dimension=MODEL_DIMS[model_id],
        language=language,
        profile=profile,
    )


def model_cache_dir(workspace: Path, model_id: str) -> Path:
    """Return the workspace-local cache directory for a model.

    Args:
        workspace: Resolved Hebb Mind workspace directory.
        model_id: HuggingFace repository ID or local model name.

    Returns:
        Directory where the model should be stored.
    """
    return workspace / "models" / model_id


# Weight-file names that mark a sentence-transformers snapshot as loadable.
# Sharded checkpoints ship an index JSON instead of a single weights blob.
_WEIGHT_FILES = (
    "model.safetensors",
    "pytorch_model.bin",
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
)


def model_dir_complete(path: Path) -> bool:
    """Return True when a model directory is actually loadable.

    A directory counts as complete only when it has both ``config.json`` **and**
    a weight file. An interrupted ``snapshot_download`` often leaves the config
    and tokenizer behind without the (large) weights — that directory must be
    treated as *not* cached so the download is retried, otherwise
    ``SentenceTransformer`` fails with "no file named model.safetensors …".

    Args:
        path: Candidate model directory.

    Returns:
        True when the directory has a config and at least one weight file.
    """
    if not path.is_dir() or not (path / "config.json").is_file():
        return False
    return any((path / name).is_file() for name in _WEIGHT_FILES)


def workspace_model_available(workspace: Path, model_id: str) -> bool:
    """Check whether a fully-downloaded model is available in the workspace.

    Args:
        workspace: Resolved Hebb Mind workspace directory.
        model_id: HuggingFace repository ID or local model name.

    Returns:
        True when the local model directory has a config **and** weight files.
    """
    return model_dir_complete(model_cache_dir(workspace, model_id))


def resolve_region(region: str = "auto", existing_hf_endpoint: str | None = None) -> RegionSelection:
    """Resolve the model download region and HuggingFace endpoint.

    Args:
        region: Explicit region value: auto, cn, or global.
        existing_hf_endpoint: Existing configured HuggingFace endpoint.

    Returns:
        Region and endpoint selection.

    Raises:
        ValueError: If region is not one of the supported choices.
    """
    if region not in REGION_CHOICES:
        raise ValueError(f"Unsupported region: {region!r}")

    if region == "cn":
        return RegionSelection(region="cn", hf_endpoint=HF_MIRROR_ENDPOINT, source="explicit")
    if region == "global":
        return RegionSelection(region="global", hf_endpoint=None, source="explicit")

    if existing_hf_endpoint:
        normalized = existing_hf_endpoint.rstrip("/")
        if normalized == HF_MIRROR_ENDPOINT:
            return RegionSelection(region="cn", hf_endpoint=normalized, source="existing")
        return RegionSelection(region="custom", hf_endpoint=normalized, source="existing")

    official, mirror = _probe_download_endpoints()
    if official.available and mirror.available:
        if (mirror.latency_ms or float("inf")) < (official.latency_ms or float("inf")):
            return RegionSelection(region="cn", hf_endpoint=HF_MIRROR_ENDPOINT, source="probe")
        return RegionSelection(region="global", hf_endpoint=None, source="probe")
    if mirror.available:
        return RegionSelection(region="cn", hf_endpoint=HF_MIRROR_ENDPOINT, source="probe")
    if official.available:
        return RegionSelection(region="global", hf_endpoint=None, source="probe")

    return RegionSelection(
        region="global",
        hf_endpoint=None,
        source="probe-failed",
        message=(
            "Could not reach HuggingFace or hf-mirror. Keeping the official endpoint. "
            "If downloads fail in China, run: hebb setup --region cn"
        ),
    )


def prefetch_model(
    model_id: str,
    workspace: Path,
    hf_endpoint: str | None = None,
    progress_callback: ProgressCallback | None = None,
    suppress_native_progress: bool = False,
) -> Path:
    """Download a HuggingFace model into the Hebb Mind workspace.

    Redundant weight variants (ONNX, OpenVINO, TensorFlow, msgpack) are skipped.
    Built-in repositories verified to publish safetensors also skip duplicate
    ``pytorch_model.bin`` / ``rust_model.ot`` copies, while repositories without
    safetensors retain their PyTorch ``*.bin`` checkpoint.

    Args:
        model_id: HuggingFace repository ID.
        workspace: Resolved Hebb Mind workspace directory.
        hf_endpoint: Optional HuggingFace-compatible endpoint.
        progress_callback: Optional callback receiving (bytes_done, bytes_total,
            current_file_desc) on every tqdm tick. Used by the web console to
            surface real-time download progress.
        suppress_native_progress: Hide HuggingFace's tqdm rendering when the
            callback is displayed by another terminal progress UI.

    Returns:
        Local model directory.

    Raises:
        ImportError: If huggingface_hub is not installed.
        Exception: Propagates HuggingFace download failures.
    """
    from huggingface_hub import snapshot_download

    local_dir = model_cache_dir(workspace, model_id)
    local_dir.parent.mkdir(parents=True, exist_ok=True)

    old_endpoint = os.environ.get("HF_ENDPOINT")
    if hf_endpoint:
        os.environ["HF_ENDPOINT"] = hf_endpoint.rstrip("/")
    else:
        os.environ.pop("HF_ENDPOINT", None)

    # LocalEmbedder.__init__ leaves HF_HUB_OFFLINE=1 in the process if it ran
    # during app startup with a cached default model — and ``huggingface_hub``
    # caches the value of HF_HUB_OFFLINE in its ``constants`` module at import
    # time, so clearing the env var alone is not enough. Force the cached
    # constant off for the download window, then restore.
    old_offline_env = os.environ.pop("HF_HUB_OFFLINE", None)
    import huggingface_hub.constants as _hf_const

    old_offline_const = _hf_const.HF_HUB_OFFLINE
    _hf_const.HF_HUB_OFFLINE = False

    snapshot_kwargs: dict = {
        "repo_id": model_id,
        "local_dir": str(local_dir),
        "ignore_patterns": _prefetch_ignore_patterns(model_id),
    }
    if progress_callback is not None:
        from hebb.embedding.progress import make_progress_tqdm

        snapshot_kwargs["tqdm_class"] = make_progress_tqdm(
            progress_callback,
            silent=suppress_native_progress,
        )

    try:
        snapshot_download(**snapshot_kwargs)
    finally:
        if old_endpoint is None:
            os.environ.pop("HF_ENDPOINT", None)
        else:
            os.environ["HF_ENDPOINT"] = old_endpoint
        if old_offline_env is not None:
            os.environ["HF_HUB_OFFLINE"] = old_offline_env
        _hf_const.HF_HUB_OFFLINE = old_offline_const

    return local_dir


def _prefetch_ignore_patterns(model_id: str) -> list[str]:
    """Return safe redundant-file exclusions for one model repository.

    Args:
        model_id: HuggingFace repository ID.

    Returns:
        Ignore patterns that retain at least one supported PyTorch checkpoint.
    """
    patterns = list(PREFETCH_IGNORE_PATTERNS)
    if model_id in _SAFETENSORS_MODELS:
        patterns.extend(_REDUNDANT_TORCH_WEIGHT_PATTERNS)
    return patterns


def _detect_locale(environ: dict[str, str]) -> str | None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = environ.get(key)
        if value:
            return value.split(":")[0]

    loc, _encoding = locale.getlocale()
    return loc


def _language_from_locale(raw_locale: str | None) -> str:
    if not raw_locale:
        return "multi"

    normalized = raw_locale.split(".", 1)[0].split("@", 1)[0].lower()
    if normalized in ("c", "posix"):
        return "multi"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("zh"):
        return "zh"
    return "multi"


def _probe_download_endpoints(timeout: float = 2.0) -> tuple[ProbeResult, ProbeResult]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        official_future = executor.submit(_probe_endpoint, "global", HF_OFFICIAL_ENDPOINT, timeout)
        mirror_future = executor.submit(_probe_endpoint, "cn", HF_MIRROR_ENDPOINT, timeout)
        return official_future.result(), mirror_future.result()


def _probe_endpoint(region: str, endpoint: str, timeout: float) -> ProbeResult:
    started = time.perf_counter()
    try:
        response = httpx.get(endpoint, timeout=timeout, follow_redirects=True)
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(
            region=region,
            endpoint=endpoint,
            available=response.status_code < 500,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return ProbeResult(region=region, endpoint=endpoint, available=False, latency_ms=None, error=str(exc))
