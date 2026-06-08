"""Anti-CSRF / drive-by guard for the local server.

The server ships with no authentication because it is meant to bind loopback
(``settings.host == "127.0.0.1"``) and be reached only by the same-origin web
console, the CLI, the MCP server, and the Claude Code / Codex hooks. The one
remaining browser-borne threat is a *malicious webpage* the user happens to have
open: it can issue cross-origin ``fetch`` calls to ``http://127.0.0.1:8321`` and,
with a permissive CORS policy, read memories, change config, or exfiltrate the
revealed LLM key (CSRF / drive-by / DNS-rebinding).

The guard is deliberately lightweight: a browser always attaches an ``Origin``
header to state-changing and cross-site requests. We reject any request whose
``Origin`` is present and is *not* one of the console's own loopback origins.
Requests without an ``Origin`` header (CLI, MCP, server-to-server) pass through,
so non-browser UX is untouched while the cross-site browser attack is closed.

The guard is registered as a single ASGI middleware in ``hebb.server.app`` so it
covers every router (no per-route auth — see INT-1).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Methods that mutate state always go through the guard.
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Read-only paths that nonetheless leak secrets or hit external URLs, so a
# cross-origin GET must be rejected even though the method looks safe. Matched
# as a suffix of the request path (the router is mounted under a prefix).
_SENSITIVE_GET_SUFFIXES = ("/config/reveal/",)


def _is_guarded(method: str, path: str) -> bool:
    """Return True if this request must be origin-checked.

    Args:
        method: HTTP method, upper-case.
        path: Request URL path.

    Returns:
        True for state-changing methods and for read-only paths that expose
        secrets (``/config/reveal/...``) or contact attacker-controlled URLs
        (``/config/test...``); False otherwise.
    """
    if method in _STATE_CHANGING_METHODS:
        return True
    if any(suffix in path for suffix in _SENSITIVE_GET_SUFFIXES):
        return True
    # /config/test-llm, /config/test-embedding etc. are POST (caught above), but
    # guard any test* path defensively regardless of method.
    return "/config/test" in path


class AntiCsrfMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin browser requests to state-changing/sensitive routes.

    A same-origin console fetch and any non-browser client (no ``Origin``
    header) pass. A request whose ``Origin`` is set and not in the allowed
    console origins is rejected with HTTP 403. The allowed-origins list is read
    from ``request.app.state.settings`` per request so it tracks config changes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply the origin check, then delegate to the next handler.

        Args:
            request: The incoming request.
            call_next: The downstream ASGI handler.

        Returns:
            A 403 ``JSONResponse`` for a disallowed cross-origin request,
            otherwise the downstream response.
        """
        origin = request.headers.get("origin")
        if origin and _is_guarded(request.method.upper(), request.url.path):
            allowed = _allowed_origins(request)
            if origin not in allowed:
                logger.warning(
                    "Rejected cross-origin request: origin=%s method=%s path=%s",
                    origin,
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Cross-origin request rejected. The Hebb Mind console API only accepts "
                            "same-origin browser requests."
                        )
                    },
                )
        return await call_next(request)


def _allowed_origins(request: Request) -> list[str]:
    """Resolve the allowed console origins for this request.

    Args:
        request: The incoming request (used to reach ``app.state.settings``).

    Returns:
        The configured loopback console origins, or an empty list if settings
        are not yet available (startup race — fail closed for guarded routes).
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return []
    origins: list[str] = settings.allowed_origins()
    return origins
