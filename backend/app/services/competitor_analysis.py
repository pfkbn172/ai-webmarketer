"""競合パターン分析。citation_logs.cited_urls の頻出ドメインを集計して、
登録済 competitors と区別して「準競合候補」として可視化する。
"""

import uuid
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.citation_log import CitationLog
from app.db.models.competitor import Competitor


def _domain_of(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


# 引用頻出だが「競合」ではないドメイン(行政・大手プラットフォーム等)
EXCLUDE_DOMAINS = (
    "city.osaka.lg.jp",
    "pref.osaka.lg.jp",
    "go.jp",
    "google.com",
    "wikipedia.org",
    "indeed.com",
    "doda.jp",
    "rikunabi.com",
    "navitime.co.jp",
    "facebook.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
)


async def analyze_competitor_patterns(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    lookback_days: int = 30,
    top_n: int = 15,
) -> list[dict]:
    """頻出ドメイン上位 N を返す。既登録 competitors と除外ドメインは別ラベル。"""
    end = date.today()
    start = end - timedelta(days=lookback_days)

    logs = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    counter: Counter[str] = Counter()
    for log_ in logs:
        for u in log_.cited_urls or []:
            d = _domain_of(u)
            if d:
                counter[d] += 1

    registered = {
        c.domain
        for c in (
            await session.scalars(
                select(Competitor).where(Competitor.tenant_id == tenant_id)
            )
        ).all()
    }

    out: list[dict] = []
    for domain, count in counter.most_common(top_n * 2):
        is_excluded = any(domain.endswith(e) or e in domain for e in EXCLUDE_DOMAINS)
        is_registered = domain in registered or any(
            domain.endswith(r) or r in domain for r in registered
        )
        if is_excluded:
            label = "excluded"
        elif is_registered:
            label = "registered_competitor"
        else:
            label = "candidate"
        out.append({"domain": domain, "count": count, "label": label})
        if len([x for x in out if x["label"] != "excluded"]) >= top_n:
            break
    return out
