"""Request guard for the local Echo API: Host check, Origin check on writes, and body-size caps.

Added to the app before CORS, so it sees every HTTP request. It is pure ASGI so it can count
body bytes as they arrive. A request that fails a check never reaches a route, so no model
is called for it. A missing Origin header is allowed, which keeps curl working. Websocket
scopes pass through unchanged; the app has no websocket routes.
"""

from __future__ import annotations

from collections.abc import Sequence

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MEBIBYTE = 1024 * 1024
KIBIBYTE = 1024
PHOTO_BODY_CAP_BYTES = int(5.5 * MEBIBYTE)
JSON_BODY_CAP_BYTES = 256 * KIBIBYTE
PHOTO_ROUTES = frozenset({"/api/read-photo", "/api/worksheet/read"})
ALLOWED_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HOST_HEADER = b"host"
ORIGIN_HEADER = b"origin"
CONTENT_LENGTH_HEADER = b"content-length"
HOST_REJECTED = {"error": "host not allowed"}
ORIGIN_REJECTED = {"error": "origin not allowed"}
BODY_TOO_LARGE = {"error": "request body is too large"}
STATUS_BAD_REQUEST = 400
STATUS_FORBIDDEN = 403
STATUS_TOO_LARGE = 413


def _header_values(scope: Scope, name: bytes) -> list[str]:
    return [value.decode("latin-1") for key, value in scope.get("headers", []) if key == name]


def _host_allowed(scope: Scope) -> bool:
    """Exactly one Host header whose name (port removed) is localhost or 127.0.0.1."""
    hosts = _header_values(scope, HOST_HEADER)
    return len(hosts) == 1 and hosts[0].split(":", 1)[0] in ALLOWED_HOSTNAMES


def _origin_allowed(scope: Scope, allowed_origins: frozenset[str]) -> bool:
    """True when no Origin header is sent, or every Origin header is an allowed origin."""
    return all(origin in allowed_origins for origin in _header_values(scope, ORIGIN_HEADER))


def _body_cap(path: str) -> int:
    return PHOTO_BODY_CAP_BYTES if path in PHOTO_ROUTES else JSON_BODY_CAP_BYTES


def _declared_length_too_big(scope: Scope, cap: int) -> bool:
    """True when a Content-Length header declares more than cap. A malformed value is ignored;
    the streamed byte count still applies."""
    try:
        declared = [int(value) for value in _header_values(scope, CONTENT_LENGTH_HEADER)]
    except ValueError:
        return False
    return any(length > cap for length in declared)


async def _read_capped_body(receive: Receive, cap: int) -> bytes | None:
    """The whole request body, or None as soon as the bytes received pass cap."""
    chunks: list[bytes] = []
    received = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            return b"".join(chunks)
        chunk = message.get("body", b"")
        received += len(chunk)
        if received > cap:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks)


def _replayed(body: bytes, receive: Receive) -> Receive:
    """A receive that yields the already-read body once, then defers to the original receive."""
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


async def _reply(
    scope: Scope, receive: Receive, send: Send, status: int, content: dict[str, str]
) -> None:
    await JSONResponse(status_code=status, content=content)(scope, receive, send)


class LocalGuard:
    """Rejects non-local Host headers, cross-site writes, and oversized bodies before any route runs."""

    def __init__(self, app: ASGIApp, allowed_origins: Sequence[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not _host_allowed(scope):
            await _reply(scope, receive, send, STATUS_BAD_REQUEST, HOST_REJECTED)
            return
        if scope["method"] not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        if not _origin_allowed(scope, self.allowed_origins):
            await _reply(scope, receive, send, STATUS_FORBIDDEN, ORIGIN_REJECTED)
            return
        await self._guard_body(scope, receive, send)

    async def _guard_body(self, scope: Scope, receive: Receive, send: Send) -> None:
        cap = _body_cap(scope["path"])
        if _declared_length_too_big(scope, cap):
            await _reply(scope, receive, send, STATUS_TOO_LARGE, BODY_TOO_LARGE)
            return
        body = await _read_capped_body(receive, cap)
        if body is None:
            await _reply(scope, receive, send, STATUS_TOO_LARGE, BODY_TOO_LARGE)
            return
        await self.app(scope, _replayed(body, receive), send)
