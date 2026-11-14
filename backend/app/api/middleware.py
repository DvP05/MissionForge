"""Pure-ASGI request body size limit (architecture 13).

Enforced on the declared Content-Length and on the bytes actually streamed, so a lying or
chunked client cannot bypass it. Exceeding the limit raises a 413 HTTPException while the
route reads the body, which the envelope handler turns into PAYLOAD_TOO_LARGE.
"""

from collections.abc import Mapping

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(
        self, app: ASGIApp, max_bytes: int, path_limits: Mapping[str, int] | None = None
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        # Exact-path overrides (e.g. mission packages carry whole runs and exceed the default).
        self.path_limits = dict(path_limits or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.path_limits.get(scope.get("path", ""), self.max_bytes)
        declared_too_big = False
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared_too_big = int(value) > limit
                except ValueError:
                    declared_too_big = True
                break

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            if declared_too_big:
                raise HTTPException(status_code=413)
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413)
            return message

        await self.app(scope, limited_receive, send)
