import asyncio

import pytest

from app.utils.retry import retry_async


async def test_succeeds_on_first_attempt() -> None:
    calls = 0

    @retry_async(max_attempts=3, base_delay=0.01)
    async def f() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert await f() == "ok"
    assert calls == 1


async def test_retries_then_succeeds() -> None:
    calls = 0

    @retry_async(max_attempts=3, base_delay=0.01, retriable_exceptions=(ValueError,))
    async def f() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ValueError("transient")
        return "ok"

    assert await f() == "ok"
    assert calls == 2


async def test_raises_after_max_attempts() -> None:
    calls = 0

    @retry_async(max_attempts=3, base_delay=0.01, retriable_exceptions=(ValueError,))
    async def f() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        await f()
    assert calls == 3


async def test_does_not_retry_unlisted_exception() -> None:
    calls = 0

    @retry_async(max_attempts=3, base_delay=0.01, retriable_exceptions=(ValueError,))
    async def f() -> None:
        nonlocal calls
        calls += 1
        raise TypeError("not retriable")

    with pytest.raises(TypeError):
        await f()
    assert calls == 1


async def test_backoff_delay_scales(monkeypatch: pytest.MonkeyPatch) -> None:
    """delay が attempt とともに指数的に増えることを確認。

    実時間の sleep を計測すると flaky なので、asyncio.sleep をモック化して引数を記録する。
    """
    delays: list[float] = []

    async def fake_sleep(d: float) -> None:
        delays.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = 0

    @retry_async(
        max_attempts=4, base_delay=1.0, max_delay=100.0, backoff_factor=2.0, jitter=0.0,
        retriable_exceptions=(ValueError,),
    )
    async def f() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("x")

    with pytest.raises(ValueError):
        await f()

    assert calls == 4
    # attempts 1,2,3 で sleep が 3 回呼ばれ、各々 1.0 / 2.0 / 4.0 秒(jitter 0)
    assert delays == [1.0, 2.0, 4.0]
