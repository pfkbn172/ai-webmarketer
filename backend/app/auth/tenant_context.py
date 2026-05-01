"""リクエストごとの tenant_id / user_id / request_id を保持する contextvar 群。

FastAPI のミドルウェア(`auth/middleware.py`)が認証時に set_tenant() を呼び、
DB セッション(`db/base.py`)が `SET LOCAL app.tenant_id` 発行時に get_tenant_id() を読む。
ロガー(`utils/logger.py`)も同じ contextvar を読み、全ログに自動付与する。

ContextVar は asyncio タスクごとに独立しているため、複数同時リクエストでも混線しない。
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    request_id: str


_EMPTY = TenantContext(tenant_id=None, user_id=None, request_id="-")
_ctx: ContextVar[TenantContext] = ContextVar("marketer_tenant_ctx", default=_EMPTY)


def set_context(
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    request_id: str,
) -> None:
    _ctx.set(TenantContext(tenant_id=tenant_id, user_id=user_id, request_id=request_id))


def clear_context() -> None:
    _ctx.set(_EMPTY)


def get_context() -> TenantContext:
    return _ctx.get()


def get_tenant_id() -> uuid.UUID | None:
    return _ctx.get().tenant_id


def get_user_id() -> uuid.UUID | None:
    return _ctx.get().user_id


def get_request_id() -> str:
    return _ctx.get().request_id


def require_tenant_id() -> uuid.UUID:
    """tenant_id が必ず設定されている前提のコードから呼ぶ。未設定なら RuntimeError。"""
    tid = _ctx.get().tenant_id
    if tid is None:
        raise RuntimeError(
            "TenantContext.tenant_id is not set. "
            "Auth middleware が動作していない、またはテナント未選択のリクエストです。"
        )
    return tid
