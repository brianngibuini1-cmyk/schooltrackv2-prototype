"""Public-demo safety middleware.

This module contains no authentication system: SchoolTrack is a single-owner
prototype. The demo guard reduces accidental or casual abuse on a public demo
and can make the demo read-only, but it is not a substitute for real access
control on a production financial system.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from .db import WRITE_METHODS

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    """Add conservative browser headers to every response."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
                headers.setdefault(
                    "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
                )
                headers.setdefault("Content-Security-Policy", CSP)
                request_headers = dict(scope.get("headers", []))
                if request_headers.get(b"x-forwarded-proto") == b"https":
                    headers.setdefault(
                        "Strict-Transport-Security",
                        "max-age=31536000; includeSubDomains",
                    )
                if scope.get("path", "").startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Reject oversized JSON/API bodies before they reach the app.

    Content-Length is checked immediately. Write requests without a length
    (for example chunked requests) are buffered with a hard byte cap.
    """

    def __init__(self, app, max_bytes: int = 256 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        method = scope.get("method", "GET").upper()
        if method not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        full_body = b"".join(chunks)
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": full_body,
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _reject(self, scope, receive, send) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "message": "That request is too large for this demonstration.",
                    "fields": {},
                }
            },
        )
        await response(scope, receive, send)


class SlidingWindowRateLimiter:
    """Small in-process limiter suitable for a single free-tier web process.

    Render's free web service runs one instance, so an in-memory limiter is
    sufficient for this demo. A multi-instance deployment would need a shared
    store such as Redis.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        *,
        clock=time.monotonic,
    ) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self.clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = self.clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, math.ceil(self.window_seconds - (now - events[0])))
                return False, retry_after
            events.append(now)
            if len(self._events) > 10_000:
                self._prune(cutoff)
            return True, 0

    def _prune(self, cutoff: float) -> None:
        stale = [
            key
            for key, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in stale:
            self._events.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class DemoGuardMiddleware:
    """Make demo writes explicit and rate-limited without an account system."""

    def __init__(
        self,
        app,
        *,
        demo_mode: bool,
        writes_enabled: bool,
        limiter: SlidingWindowRateLimiter | None,
        trust_proxy_headers: bool,
    ) -> None:
        self.app = app
        self.demo_mode = demo_mode
        self.writes_enabled = writes_enabled
        self.limiter = limiter
        self.trust_proxy_headers = trust_proxy_headers

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.demo_mode:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if method not in WRITE_METHODS or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        if not self.writes_enabled:
            response = JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "message": (
                            "This is a read-only demonstration. Creating and "
                            "approving records is disabled."
                        ),
                        "fields": {},
                    }
                },
            )
            await response(scope, receive, send)
            return

        if self.limiter is not None:
            allowed, retry_after = self.limiter.check(self._client_ip(scope))
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "error": {
                            "message": (
                                "Too many changes from this browser. Please wait "
                                "a moment and try again."
                            ),
                            "fields": {},
                        }
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

    def _client_ip(self, scope) -> str:
        if self.trust_proxy_headers:
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            forwarded = headers.get(b"x-forwarded-for")
            if forwarded:
                return forwarded.decode("latin-1").split(",")[0].strip() or "unknown"
        client = scope.get("client")
        return client[0] if client else "unknown"
