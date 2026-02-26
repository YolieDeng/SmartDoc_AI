from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """简单的 API Key 校验中间件。
    如果 API_KEY 未配置（空字符串），则跳过校验。
    """

    async def dispatch(self, request: Request, call_next):
        api_key = get_settings().api_key
        if not api_key:
            return await call_next(request)

        # 放行 docs 和 openapi
        if request.url.path in ("/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        token = request.headers.get("X-API-Key", "")
        if token != api_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        return await call_next(request)
