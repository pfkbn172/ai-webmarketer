"""認証 E2E フロー: login → /me → logout を実 DB で検証。

- ユーザーを作成 → ログイン → Cookie を受け取る
- /me が 200 になる
- 不正 password だと 401
- logout 後は /me が 401
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.password import hash_password
from app.db.models.enums import UserRoleEnum
from app.db.models.user import User
from app.main import app
from app.settings import settings
from tests.integration.conftest import _has_postgres

pytestmark = pytest.mark.skipif(not _has_postgres(), reason="実 PostgreSQL が必要")


@pytest_asyncio.fixture
async def admin_user() -> AsyncIterator[tuple[User, str]]:
    """テスト用 admin ユーザー。終了時に DELETE で掃除。

    AsyncClient の login は app の engine を使うため、ユーザーは独立した engine で
    commit する必要がある(同 DB なので RLS バイパスのために users テーブルは RLS 対象外)。
    """
    password = "test-password-1234"
    email = f"admin+{uuid.uuid4().hex[:8]}@example.com"

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    user_id: uuid.UUID
    async with factory() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRoleEnum.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        user_id = user.id

    # ユーザーオブジェクトの最低限の情報だけ持って渡す
    yield user, password

    async with factory() as session:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
        await session.commit()
    await engine.dispose()


async def test_login_me_logout_flow(admin_user: tuple[User, str]) -> None:
    user, password = admin_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. login
        r = await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": password}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == str(user.id)
        assert body["role"] == "admin"
        assert "marketer_access" in r.cookies

        # 2. /me with cookies
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == user.email
        assert me["role"] == "admin"

        # 3. logout
        r = await client.post("/api/v1/auth/logout")
        assert r.status_code == 204

        # 4. cookie が消えたので /me は 401
        client.cookies.clear()
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401


async def test_login_with_wrong_password_returns_401(admin_user: tuple[User, str]) -> None:
    user, _ = admin_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
        )
        assert r.status_code == 401


async def test_me_without_auth_returns_401() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401
