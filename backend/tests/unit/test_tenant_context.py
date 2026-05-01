import asyncio
import uuid

import pytest

from app.auth.tenant_context import (
    clear_context,
    get_context,
    get_tenant_id,
    require_tenant_id,
    set_context,
)


def test_default_context_is_empty() -> None:
    clear_context()
    ctx = get_context()
    assert ctx.tenant_id is None
    assert ctx.user_id is None
    assert ctx.request_id == "-"


def test_set_and_get_context() -> None:
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    set_context(tenant_id=tid, user_id=uid, request_id="req-abc")
    ctx = get_context()
    assert ctx.tenant_id == tid
    assert ctx.user_id == uid
    assert ctx.request_id == "req-abc"
    assert get_tenant_id() == tid


def test_require_tenant_id_raises_when_unset() -> None:
    clear_context()
    with pytest.raises(RuntimeError, match="tenant_id is not set"):
        require_tenant_id()


def test_context_isolated_between_tasks() -> None:
    """asyncio タスクごとに ContextVar が独立していることを確認(マルチテナント分離の前提)。"""

    async def task(tid: uuid.UUID, expected: uuid.UUID) -> None:
        set_context(tenant_id=tid, user_id=None, request_id="t")
        await asyncio.sleep(0.01)
        assert get_tenant_id() == expected

    async def main() -> None:
        a = uuid.uuid4()
        b = uuid.uuid4()
        await asyncio.gather(task(a, a), task(b, b))

    asyncio.run(main())
