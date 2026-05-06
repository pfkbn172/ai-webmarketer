"""Google / Bing のサジェスト API からキーワード派生語を取得する。

Google: https://suggestqueries.google.com/complete/search
Bing  : https://api.bing.com/osjson.aspx

どちらも JSON 配列の2要素目に派生語リストが入る OpenSearch 互換形式。
レート制限・429 はリトライ→規定回数超過なら空リストで返す(ジョブ全体は完走)。
"""

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

from app.keyword_engine.normalizer import normalize
from app.utils.logger import get_logger

log = get_logger(__name__)


GOOGLE_BASE_URL = "https://suggestqueries.google.com/complete/search"
BING_BASE_URL = "https://api.bing.com/osjson.aspx"

USER_AGENT = "Mozilla/5.0 (compatible; kiseeeen-marketer/1.0)"

DEFAULT_TIMEOUT = 8.0  # サジェストは高速なので短めで十分
MAX_RETRIES = 3
BACKOFF_BASE_S = 1.0


@dataclass(frozen=True, slots=True)
class SuggestResult:
    source: Literal["google_suggest", "bing_suggest"]
    seed: str
    derived: tuple[str, ...]  # 正規化済みの派生語


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
) -> list[str] | None:
    """OpenSearch JSON `[seed, [d1, d2, ...]]` を返す。失敗時は None。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"},
            )
            if resp.status_code == 429:
                log.warning("suggest_rate_limited", url=url, attempt=attempt)
                await asyncio.sleep(BACKOFF_BASE_S * (2 ** (attempt - 1)))
                continue
            resp.raise_for_status()
            data = resp.json()
            if (
                isinstance(data, list)
                and len(data) >= 2
                and isinstance(data[1], list)
            ):
                return [str(x) for x in data[1] if x]
            log.warning("suggest_unexpected_payload", url=url, payload_head=str(data)[:120])
            return None
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            log.warning(
                "suggest_fetch_failed", url=url, attempt=attempt, error=str(exc)
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_BASE_S * (2 ** (attempt - 1)))
    return None


async def fetch_google_suggest(
    seed: str, *, client: httpx.AsyncClient | None = None
) -> SuggestResult:
    """Google サジェストから派生語を取る(日本語・hl=ja)。"""
    params = {"client": "firefox", "hl": "ja", "q": seed}
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    try:
        derived = await _fetch_with_retry(client, GOOGLE_BASE_URL, params)
    finally:
        if own_client:
            await client.aclose()
    if derived is None:
        return SuggestResult(source="google_suggest", seed=seed, derived=())
    norm = tuple(dict.fromkeys(normalize(x) for x in derived if x))  # 重複排除・順序維持
    return SuggestResult(source="google_suggest", seed=seed, derived=norm)


async def fetch_bing_suggest(
    seed: str, *, client: httpx.AsyncClient | None = None
) -> SuggestResult:
    """Bing サジェストから派生語を取る(日本市場・mkt=ja-JP)。"""
    params = {"query": seed, "mkt": "ja-JP"}
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    try:
        derived = await _fetch_with_retry(client, BING_BASE_URL, params)
    finally:
        if own_client:
            await client.aclose()
    if derived is None:
        return SuggestResult(source="bing_suggest", seed=seed, derived=())
    norm = tuple(dict.fromkeys(normalize(x) for x in derived if x))
    return SuggestResult(source="bing_suggest", seed=seed, derived=norm)


async def fetch_both(seed: str) -> tuple[SuggestResult, SuggestResult]:
    """Google + Bing を並列で取得する。1接続を共有して効率化。"""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        return await asyncio.gather(
            fetch_google_suggest(seed, client=client),
            fetch_bing_suggest(seed, client=client),
        )
