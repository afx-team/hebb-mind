"""Custom HTTP embedding provider — user-defined method/url/headers/body.

This backs the console "Custom HTTP (JSON)" embedding sub-mode. Unlike the
litellm-based :class:`~hebb.embedding.api.ApiEmbedder`, the entire request is
specified by the user, so non-OpenAI-shaped endpoints (internal services,
gateways, bespoke model servers) can be plugged in without code changes.

Request body
------------
``body_template`` is a JSON template containing exactly one placeholder:

- ``{{input}}`` — replaced with a JSON array of every text in the batch, so
  the whole batch goes out in a single request. Example template::

      {"model": "my-embed", "input": {{input}}}

- ``{{text}}`` — replaced with a single JSON-escaped string; one request is
  issued per text. Use this for endpoints that only accept one input::

      {"text": {{text}}}

Response extraction
-------------------
``response_path`` is a dot-separated path into the JSON response with ``*`` as
an array wildcard. The default ``data.*.embedding`` matches the OpenAI shape
``{"data": [{"embedding": [...]}, ...]}``. A path may resolve to a single
vector (``data.0.embedding``) or, via ``*``, a list of vectors.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

INPUT_TOKEN = "{{input}}"
TEXT_TOKEN = "{{text}}"


def _l2_normalize(vector: list[float]) -> list[float]:
    """Return ``vector`` scaled to unit L2 norm.

    The vector-store cosine conversion (``cosine = 1 - d²/2``) only holds for
    unit vectors, so every provider must return normalized embeddings. A
    zero (or empty) vector is returned unchanged to avoid division by zero.

    Args:
        vector: The raw embedding to normalize.

    Returns:
        The unit-norm embedding, or the input unchanged if its norm is zero.
    """
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


def parse_headers(raw: str | None) -> dict[str, str]:
    """Parse the configured headers JSON string into a dict.

    Args:
        raw: A JSON object string, or ``None``/empty for no extra headers.

    Returns:
        The parsed headers mapping (empty if ``raw`` is falsy).

    Raises:
        ValueError: If ``raw`` is not a JSON object.
    """
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"embedding_http_headers is not valid JSON: {e}") from e
    if not isinstance(parsed, dict):
        raise ValueError("embedding_http_headers must be a JSON object")
    return {str(k): str(v) for k, v in parsed.items()}


def _resolve_path(obj: Any, segments: list[str]) -> Any:
    """Walk ``obj`` following dot-path ``segments`` with ``*`` array wildcards."""
    if not segments:
        return obj
    seg, rest = segments[0], segments[1:]

    if seg == "*":
        if not isinstance(obj, list):
            raise ValueError(f"response path '*' expected a list, got {type(obj).__name__}")
        return [_resolve_path(item, rest) for item in obj]

    if isinstance(obj, list):
        try:
            idx = int(seg)
        except ValueError as e:
            raise ValueError(f"response path segment '{seg}' is not a list index") from e
        if not -len(obj) <= idx < len(obj):
            raise ValueError(f"response path index {idx} out of range (len={len(obj)})")
        return _resolve_path(obj[idx], rest)

    if isinstance(obj, dict):
        if seg not in obj:
            raise ValueError(f"response path key '{seg}' not found (have: {list(obj)})")
        return _resolve_path(obj[seg], rest)

    raise ValueError(f"response path '{seg}' cannot descend into {type(obj).__name__}")


def _is_vector(x: Any) -> bool:
    return isinstance(x, list) and bool(x) and all(isinstance(v, (int, float)) for v in x)


def extract_vectors(response: Any, response_path: str) -> list[list[float]]:
    """Extract a list of float vectors from ``response`` at ``response_path``.

    A path resolving to a single numeric vector yields a one-element list; a
    path with a ``*`` wildcard yields one entry per array element.

    Raises:
        ValueError: If the path does not resolve to a vector or list of vectors.
    """
    segments = [s for s in response_path.split(".") if s != ""]
    resolved = _resolve_path(response, segments)

    if _is_vector(resolved):
        return [[float(v) for v in resolved]]
    if isinstance(resolved, list) and all(_is_vector(item) for item in resolved):
        return [[float(v) for v in item] for item in resolved]
    raise ValueError(
        f"response_path '{response_path}' did not resolve to a vector or list of vectors "
        f"(got {type(resolved).__name__})"
    )


def render_body(body_template: str, *, texts: list[str]) -> tuple[Any, bool]:
    """Render the body template for a batch of texts.

    Returns ``(payload, batched)`` where ``payload`` is the parsed JSON body and
    ``batched`` is ``True`` when the template uses ``{{input}}`` (the whole batch
    in one request) or ``False`` when it uses ``{{text}}`` (caller loops per text).

    For the ``{{text}}`` case exactly one text must be supplied.

    Raises:
        ValueError: If no placeholder is present or the rendered body is invalid JSON.
    """
    if INPUT_TOKEN in body_template:
        rendered = body_template.replace(INPUT_TOKEN, json.dumps(texts))
        return _parse_rendered(rendered), True
    if TEXT_TOKEN in body_template:
        if len(texts) != 1:
            raise ValueError("render_body with {{text}} expects exactly one text")
        rendered = body_template.replace(TEXT_TOKEN, json.dumps(texts[0]))
        return _parse_rendered(rendered), False
    raise ValueError(f"body template must contain {INPUT_TOKEN} or {TEXT_TOKEN}")


def _parse_rendered(rendered: str) -> Any:
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as e:
        raise ValueError(f"rendered request body is not valid JSON: {e}") from e


class CustomHttpEmbedder:
    """Embedding provider that calls a fully user-defined HTTP endpoint."""

    def __init__(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body_template: str,
        response_path: str = "data.*.embedding",
        dimension: int = 0,
        timeout: float = 30.0,
    ) -> None:
        self.method = (method or "POST").upper()
        self.url = url
        self.headers = headers
        self.body_template = body_template
        self.response_path = response_path or "data.*.embedding"
        self._dimension = dimension
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        if INPUT_TOKEN not in body_template and TEXT_TOKEN not in body_template:
            raise ValueError(f"body template must contain {INPUT_TOKEN} or {TEXT_TOKEN}")
        self._per_text = INPUT_TOKEN not in body_template
        logger.info(
            "CustomHttpEmbedder initialized: %s %s (per_text=%s, response_path=%s)",
            self.method,
            self.url,
            self._per_text,
            self.response_path,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    def set_dimension(self, dim: int) -> None:
        """Record the dimension detected by a probe request."""
        self._dimension = dim

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _request(self, payload: Any) -> Any:
        client = self._get_client()
        resp = await client.request(self.method, self.url, json=payload, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def embed(self, text: str) -> list[float]:
        vectors = await self.embed_batch([text])
        return vectors[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self._per_text:
            payload, _ = render_body(self.body_template, texts=texts)
            response = await self._request(payload)
            vectors = extract_vectors(response, self.response_path)
            if len(vectors) != len(texts):
                raise ValueError(
                    f"custom HTTP embedding returned {len(vectors)} vectors for {len(texts)} inputs; "
                    "check the response_path and that the endpoint preserves input order"
                )
            return [_l2_normalize(v) for v in vectors]

        # Per-text mode: one request per input via the {{text}} placeholder.
        out: list[list[float]] = []
        for text in texts:
            payload, _ = render_body(self.body_template, texts=[text])
            response = await self._request(payload)
            vectors = extract_vectors(response, self.response_path)
            out.append(_l2_normalize(vectors[0]))
        return out

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` if one was opened.

        Safe to call multiple times; the client handle is cleared so a
        subsequent embed call lazily re-creates it.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None
