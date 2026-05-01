"""認証ミドルウェア。

W1-06 段階の責務:
- すべてのリクエストに request_id を発行(X-Request-ID ヘッダで返却)
- Cookie / Authorization ヘッダから JWT を取り出し、検証して TenantContext に詰める
- public エンドポイントはトークン無しでも通す

JWT 検証失敗時は 401 を返さず、TenantContext を未設定のまま続行する。
個別エンドポイントが Depends で require_user / require_admin を要求して 401 を返す方針。
これにより public 系の判定をミドルウェアで持つ必要がなくなる(public パスは PUBLIC_PATHS で
ドキュメント化のみ)。
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.jwt import TokenError, decode_token
from app.auth.tenant_context import clear_context, set_context

PUBLIC_PATHS: frozenset[str] = frozenset({
    "/api/v1/healthz",
    "/api/v1/readyz",
    "/api/v1/auth/login",
    "/api/docs",
    "/api/openapi.json",
})

ACCESS_TOKEN_COOKIE = "marketer_access"
REFRESH_TOKEN_COOKIE = "marketer_refresh"


def _extract_token(request: Request) -> str | None:
    """Cookie 優先、無ければ Authorization: Bearer ヘッダから取り出す。"""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        return token
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(None, 1)[1].strip()
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """認証 + リクエストコンテキスト設定。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]

        tenant_id: uuid.UUID | None = None
        user_id: uuid.UUID | None = None

        token = _extract_token(request)
        if token:
            try:
                claims = decode_token(token)
                if claims.token_type == "access":
                    user_id = claims.user_id
                    tenant_id = claims.tenant_id
            except TokenError:
                # トークン不正は context を空のまま進める(個別エンドポイントが 401 を出す)
                pass

        set_context(tenant_id=tenant_id, user_id=user_id, request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_context()

        response.headers["x-request-id"] = request_id
        return response


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/api/docs")
