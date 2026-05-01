"""認証ミドルウェア。

W1-04 段階の責務:
- すべてのリクエストに request_id を発行(X-Request-ID ヘッダで返却)
- TenantContext.request_id を設定(ロガーが拾う)
- JWT 検証は W1-06 で追加(現状は Cookie / Authorization ヘッダの存在チェックのみ)

W1-06 で本実装:
- Authorization: Bearer <jwt> または Cookie からトークン取り出し
- 署名検証 + 期限チェック
- claims から user_id / tenant_id を読み TenantContext に詰める
- public エンドポイント(/healthz, /readyz, /api/v1/auth/login)はスキップ
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.tenant_context import clear_context, set_context

PUBLIC_PATHS: frozenset[str] = frozenset({
    "/api/v1/healthz",
    "/api/v1/readyz",
    "/api/v1/auth/login",
    "/api/docs",
    "/api/openapi.json",
})


class AuthMiddleware(BaseHTTPMiddleware):
    """認証 + リクエストコンテキスト設定。

    順序: AuthMiddleware → エンドポイント → 後処理(ヘッダ付与)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]

        # W1-06 で JWT デコード結果を入れる
        tenant_id: uuid.UUID | None = None
        user_id: uuid.UUID | None = None

        set_context(tenant_id=tenant_id, user_id=user_id, request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_context()

        response.headers["x-request-id"] = request_id
        return response


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/api/docs")
