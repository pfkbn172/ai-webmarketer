"""主要 API エンドポイントの統合テスト。

実 PostgreSQL + 認証 + RLS を通して E2E に近い動作を確認する。
- /api/v1/tenants/me
- /api/v1/target-queries CRUD
- /api/v1/citation-logs/summary
- /api/v1/kpi/summary
- /api/v1/exports/<kind>.csv
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
async def admin_with_tenant() -> AsyncIterator[tuple[User, uuid.UUID, str]]:
    """admin ユーザー + テナント 1 つ + user_tenants 紐付け。"""
    password = "test-password-1234"
    email = f"admin+{uuid.uuid4().hex[:8]}@example.com"
    tid = uuid.uuid4()
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRoleEnum.admin,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        # テナント作成(RLS のため app.tenant_id を設定)
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tid)},
        )
        await session.execute(
            text(
                "INSERT INTO tenants (id, name, domain, compliance_type, is_active) "
                "VALUES (:id, :name, :domain, 'general', true)"
            ),
            {"id": str(tid), "name": f"t-{tid.hex[:6]}", "domain": "example.test"},
        )
        await session.execute(
            text("INSERT INTO user_tenants (user_id, tenant_id) VALUES (:u, :t)"),
            {"u": str(user.id), "t": str(tid)},
        )
        await session.commit()
        user_id = user.id

    yield user, tid, password

    async with factory() as session:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tid)},
        )
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(tid)})
        await session.commit()
    await engine.dispose()


async def _login(client: httpx.AsyncClient, email: str, password: str) -> None:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


async def test_tenants_me_endpoint(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)
        r = await client.get("/api/v1/tenants/me")
        assert r.status_code == 200
        data = r.json()
        assert any(t["id"] == str(tid) for t in data)


async def test_target_queries_crud(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)

        # 初期は空
        r = await client.get("/api/v1/target-queries/")
        assert r.status_code == 200
        assert r.json() == []

        # 作成
        r = await client.post("/api/v1/target-queries/", json={"query_text": "test query"})
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["query_text"] == "test query"

        # 一覧
        r = await client.get("/api/v1/target-queries/")
        assert len(r.json()) == 1

        # 削除
        r = await client.delete(f"/api/v1/target-queries/{created['id']}")
        assert r.status_code == 204

        r = await client.get("/api/v1/target-queries/")
        assert r.json() == []


async def test_citation_summary_empty(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)
        r = await client.get("/api/v1/citation-logs/summary")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


async def test_kpi_summary_empty(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)
        r = await client.get("/api/v1/kpi/summary?days=30")
        assert r.status_code == 200
        body = r.json()
        assert body["period_days"] == 30
        assert body["ai_citation_count"] == 0


async def test_export_csv(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)
        for kind in ("kpi", "citation", "contents", "inquiries", "target_queries"):
            r = await client.get(f"/api/v1/exports/{kind}.csv")
            assert r.status_code == 200
            assert r.headers.get("content-type", "").startswith("text/csv")


async def test_unknown_export_kind_returns_400(admin_with_tenant) -> None:
    user, tid, password = admin_with_tenant
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _login(client, user.email, password)
        r = await client.get("/api/v1/exports/foo.csv")
        assert r.status_code == 400
