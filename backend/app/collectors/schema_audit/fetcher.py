"""URL を取得して JSON-LD ブロックを抽出する。"""

import json

import httpx
from bs4 import BeautifulSoup

from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)


@retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
async def fetch_html(url: str, *, request_timeout: float = 30.0) -> str:
    async with httpx.AsyncClient(timeout=request_timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "AIWebMarketerBot/1.0"})
        resp.raise_for_status()
        return resp.text


def extract_jsonld_blocks(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    blocks: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks
