"""認証エンドポイント。

/api/v1/auth/login    POST  メール+パスワード → JWT を Cookie で配布
/api/v1/auth/logout   POST  Cookie 削除
/api/v1/auth/me       GET   現在のユーザー情報(認証必須)

Cookie 属性:
- httpOnly: JS からアクセス不可(XSS 耐性)
- secure: 本番のみ True(HTTPS 必須)
- samesite: lax(CSRF 軽減、ブラウザ起点のリンクは許可)
- path: /(SPA 全体で送信)
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user
from app.auth.jwt import issue_access_token, issue_refresh_token
from app.auth.middleware import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from app.auth.password import verify_password
from app.db.base import get_db_session
from app.db.repositories.user import UserRepository
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: uuid.UUID
    role: str
    tenant_id: uuid.UUID | None
    access_token_expires_at: datetime


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    tenant_ids: list[uuid.UUID]


def _set_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_expires: datetime,
    refresh_expires: datetime,
) -> None:
    is_prod = settings.env == "production"
    common = dict(httponly=True, samesite="lax", secure=is_prod, path="/")
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        expires=access_expires,
        **common,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        expires=refresh_expires,
        **common,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    repo = UserRepository(session)
    user = await repo.get_by_email(body.email)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        # 失敗時は理由を分けない(timing も近づける)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Phase 1: ユーザーが所属する最初のテナントを自動選択。複数所属時の切替 UI は W4-05。
    tenant_ids = await repo.list_tenants_for(user.id)
    selected_tenant: uuid.UUID | None = tenant_ids[0] if tenant_ids else None

    access_token, access_exp = issue_access_token(
        user_id=user.id, role=user.role.value, tenant_id=selected_tenant
    )
    refresh_token, refresh_exp = issue_refresh_token(user_id=user.id)
    _set_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires=access_exp,
        refresh_expires=refresh_exp,
    )

    return LoginResponse(
        user_id=user.id,
        role=user.role.value,
        tenant_id=selected_tenant,
        access_token_expires_at=access_exp,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> MeResponse:
    repo = UserRepository(session)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    tenant_ids = await repo.list_tenants_for(user_id)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        tenant_ids=tenant_ids,
    )
