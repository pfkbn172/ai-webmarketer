"""競合 RSS フィードを取得して最新記事を抽出。"""

from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser
import httpx

from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FeedEntry:
    title: str
    url: str
    published_at: datetime | None
    summary: str | None


async def fetch_feed(rss_url: str) -> list[FeedEntry]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(rss_url, headers={"User-Agent": "AIWebMarketerBot/1.0"})
        resp.raise_for_status()
        body = resp.text

    feed = feedparser.parse(body)
    out: list[FeedEntry] = []
    for entry in feed.entries:
        out.append(
            FeedEntry(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                published_at=_parse_date(entry),
                summary=entry.get("summary"),
            )
        )
    log.info("rss_fetched", url=rss_url, n_entries=len(out))
    return out


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        v = entry.get(key)
        if v:
            try:
                return datetime(*v[:6], tzinfo=UTC)
            except (TypeError, ValueError):
                continue
    return None
