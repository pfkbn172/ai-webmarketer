"""FastAPI Depends 用の共通依存関数。

require_user: 認証必須エンドポイント全般
require_admin: 管理者権限が必要なエンドポイント
get_current_tenant_id: テナント所属エンドポイント

全て TenantContext を介して動作する(リクエスト中に AuthMiddleware が詰めた値を読む)。
"""

import uuid

from fastapi import HTTPException, status

from app.auth.tenant_context import get_context


def require_user() -> uuid.UUID:
    """認証必須。user_id が無ければ 401。"""
    ctx = get_context()
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return ctx.user_id


def require_admin() -> uuid.UUID:
    """管理者必須。Phase 1 はミドルウェアで role を context に持っていないので、
    エンドポイント側で User を引いて role 判定する想定。本関数では現状認証必須のみ。

    W2 以降で TenantContext に role を含める拡張を検討。
    """
    return require_user()


def require_tenant_id() -> uuid.UUID:
    """テナント所属。tenant_id が context に無ければ 400(テナント未選択)。"""
    ctx = get_context()
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if ctx.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant not selected",
        )
    return ctx.tenant_id
