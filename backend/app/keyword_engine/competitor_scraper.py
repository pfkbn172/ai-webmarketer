"""競合サイトの見出し収集。

robots.txt を尊重し、トップページ + competitors.target_urls で指定された主要 LP の
title / h1 / h2 / h3 を抽出して dict で返す。失敗時は空 dict。

注意:
- 動的レンダ前提のSPAサイトには対応しない(httpx で取れる初期 HTML のみ)。
- 同一ホストに対して連続アクセスする場合は、呼び出し側で間隔を空けること。
"""

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.utils.logger import get_logger

log = get_logger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; kiseeeen-marketer/1.0; +https://kiseeeen.co.jp/)"
DEFAULT_TIMEOUT = 10.0
MAX_HEADINGS_PER_LEVEL = 30  # 1 ページから取り過ぎない上限


@dataclass(slots=True)
class HeadingsResult:
    url: str
    title: str | None = None
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    h3: list[str] = field(default_factory=list)
    error: str | None = None
    skipped_robots: bool = False

    def total(self) -> int:
        n = len(self.h1) + len(self.h2) + len(self.h3)
        if self.title:
            n += 1
        return n


async def _check_robots(url: str, client: httpx.AsyncClient) -> bool:
    """robots.txt が存在しないか fetch 失敗 → True(=許可)で進む(寛容デフォルト)。"""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return True
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = await client.get(robots_url, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200 or not resp.text.strip():
            return True
        rp = RobotFileParser()
        rp.parse(resp.text.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        # robots.txt が読めない=デフォルト許可で進める(競合公開サイト前提)。
        return True


async def fetch_headings(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    request_timeout: float = DEFAULT_TIMEOUT,
) -> HeadingsResult:
    """1 URL の見出しを取得。"""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=request_timeout, follow_redirects=True)
    try:
        if not await _check_robots(url, client):
            return HeadingsResult(url=url, skipped_robots=True)

        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "ja",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
        except httpx.HTTPError as exc:
            log.warning("competitor_fetch_failed", url=url, error=str(exc))
            return HeadingsResult(url=url, error=str(exc))

        if resp.status_code >= 400:
            log.warning("competitor_fetch_status", url=url, status=resp.status_code)
            return HeadingsResult(url=url, error=f"HTTP {resp.status_code}")

        ct = resp.headers.get("content-type", "")
        if "html" not in ct.lower():
            return HeadingsResult(url=url, error=f"non-HTML content-type: {ct}")

        try:
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            soup = BeautifulSoup(resp.text, "html.parser")

        title = (soup.title.string or "").strip() if soup.title else None
        h1 = _extract_texts(soup, "h1")
        h2 = _extract_texts(soup, "h2")
        h3 = _extract_texts(soup, "h3")
        return HeadingsResult(url=url, title=title, h1=h1, h2=h2, h3=h3)
    finally:
        if own_client:
            await client.aclose()


def _extract_texts(soup: BeautifulSoup, tag: str) -> list[str]:
    out: list[str] = []
    for el in soup.find_all(tag):
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text:
            continue
        # 異常に長いものは無視(本文が h タグに紛れた場合の安全弁)
        if len(text) > 200:
            continue
        out.append(text)
        if len(out) >= MAX_HEADINGS_PER_LEVEL:
            break
    return out


async def fetch_many(
    urls: list[str], *, per_host_delay_s: float = 5.0
) -> list[HeadingsResult]:
    """複数 URL を取得。同一ホストには per_host_delay_s 秒空ける。"""
    results: list[HeadingsResult] = []
    last_seen: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        for url in urls:
            host = urlparse(url).netloc
            if host in last_seen:
                # 直前のリクエストとの差分を計算する代わりに、同一ホストならスリープ
                await asyncio.sleep(per_host_delay_s)
            last_seen[host] = 0.0
            results.append(await fetch_headings(url, client=client))
    return results
