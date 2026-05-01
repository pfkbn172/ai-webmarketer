"""指数バックオフリトライデコレータ。

仕様書 8.1: 外部 API 呼び出しは指数バックオフで最大 3 回リトライ。
失敗時はエラーログを記録し、呼び出し元が責任を持って通知や job_execution_logs への記録を行う。

使い方:
    @retry_async(max_attempts=3, base_delay=1.0, retriable_exceptions=(httpx.HTTPError,))
    async def fetch_gsc(...):
        ...

判断基準:
- リトライ可能か否かは呼び出し元のドメイン判断。retriable_exceptions で明示する
- 4xx 系の永続エラー(401, 403, 404 等)は基本リトライしない(呼び出し元で例外を分ける)
- LLM Provider は ProviderError(retriable=True) のみリトライ
"""

import asyncio
import functools
import random
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from app.utils.logger import get_logger

log = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_async(
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.2,
    retriable_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """async 関数用の指数バックオフリトライ。

    delay = min(max_delay, base_delay * (backoff_factor ** (attempt - 1)))
            + random(0, base_delay * jitter)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retriable_exceptions as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        log.warning(
                            "retry_exhausted",
                            func=func.__qualname__,
                            attempts=attempt,
                            error=str(exc),
                        )
                        raise
                    delay = min(max_delay, base_delay * (backoff_factor ** (attempt - 1)))
                    delay += random.uniform(0, base_delay * jitter)
                    log.info(
                        "retry_scheduled",
                        func=func.__qualname__,
                        attempt=attempt,
                        next_delay_sec=round(delay, 2),
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
            # 到達しないが型のため
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
