"""PageSpeed Insights v5 API クライアント。

無料・API キーのみ。レスポンスから Lighthouse スコアと Core Web Vitals を抽出。
"""

from dataclasses import dataclass
from typing import Literal

import httpx

from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PageSpeedResult:
    page_url: str
    strategy: str  # 'mobile' | 'desktop'
    performance_score: int | None  # 0〜100
    lcp_ms: int | None
    cls: float | None
    inp_ms: int | None
    fcp_ms: int | None
    ttfb_ms: int | None


_BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def fetch(
    url: str,
    *,
    api_key: str,
    strategy: Literal["mobile", "desktop"] = "mobile",
    request_timeout: float = 60.0,
) -> PageSpeedResult:
    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": "performance",
    }
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        resp = await client.get(_BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    categories = lighthouse.get("categories", {})
    perf = categories.get("performance", {}).get("score")
    score = int(round(perf * 100)) if isinstance(perf, (int, float)) else None

    def _audit_num(key: str) -> float | None:
        a = audits.get(key)
        if not isinstance(a, dict):
            return None
        v = a.get("numericValue")
        return float(v) if isinstance(v, (int, float)) else None

    lcp = _audit_num("largest-contentful-paint")
    cls = _audit_num("cumulative-layout-shift")
    inp = _audit_num("interaction-to-next-paint") or _audit_num("experimental-interaction-to-next-paint")
    fcp = _audit_num("first-contentful-paint")
    ttfb = _audit_num("server-response-time")

    return PageSpeedResult(
        page_url=url,
        strategy=strategy,
        performance_score=score,
        lcp_ms=int(lcp) if lcp is not None else None,
        cls=round(cls, 3) if cls is not None else None,
        inp_ms=int(inp) if inp is not None else None,
        fcp_ms=int(fcp) if fcp is not None else None,
        ttfb_ms=int(ttfb) if ttfb is not None else None,
    )
