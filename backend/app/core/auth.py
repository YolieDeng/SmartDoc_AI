import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

# 不需要鉴权的路径
_PUBLIC_PATHS = {"/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware:
    """纯 ASGI 中间件，不会缓冲 response body，兼容 SSE 流式输出。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        api_key = get_settings().api_key
        if not api_key:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # 从 headers 中提取 X-API-Key
        headers = dict(scope.get("headers", []))
        token = headers.get(b"x-api-key", b"").decode()

        if token != api_key:
            body = json.dumps({"detail": "Invalid API Key"}).encode()
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await self.app(scope, receive, send)
