"""戦略レビューユースケース(月次レポートと別に単体実行可能)。

「事業文脈と数値の乖離を AI が言語化」する短い構造化レビュー。
ダッシュボードから「今すぐ戦略レビュー」ボタンで呼ばれる。

出力例:
{
  "core_findings": [
    "拠点地域系クエリ(local_district)で平均引用率 60% 達成",
    "業種特化クエリ(industry_test)では引用率 0%、競合 X が独占"
  ],
  "alignments_with_business_context": [
    "「天王寺区での実顧客獲得」strong_segments と整合"
  ],
  "misalignments": [
    "weak_segments に挙げた業種特化を検証しているのは妥当だが、コンテンツ拡充が伴っていない"
  ],
  "next_actions": [
    {"priority": 1, "action": "...", "rationale": "..."}
  ]
}
"""

import json
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.json_parse import parse_json_object
from app.ai_engine.providers.factory import AIProviderFactory
from app.db.models.citation_log import CitationLog
from app.db.models.enums import AIUseCaseEnum
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.services.anomaly_detector import detect as detect_anomalies
from app.utils.logger import get_logger

log = get_logger(__name__)


PROMPT = """あなたは中小企業向け SEO/LLMO の戦略コンサルタントです。
以下の事業者の現状について、数字と事業文脈を突き合わせた構造化レビューを行ってください。

## 事業文脈
{business_context}

## 直近 30 日のデータ
- クラスタ別引用率: {cluster_breakdown}
- 検知された違和感: {anomalies}

## 出力フォーマット(JSON)
{{
  "core_findings": ["数字から見える構造的な発見を 3 つ"],
  "alignments_with_business_context": ["事業文脈と整合している発見"],
  "misalignments": ["事業文脈とずれている兆候"],
  "next_actions": [
    {{"priority": 1, "action": "具体アクション", "rationale": "なぜそれを優先すべきか"}}
  ]
}}

JSON のみ返す。findings は具体的に、抽象論を避ける。
"""


async def _cluster_breakdown(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> dict:
    queries = list(
        (await session.scalars(select(TargetQuery).where(TargetQuery.tenant_id == tenant_id))).all()
    )
    qmap = {q.id: q.cluster_id or "unknown" for q in queries}
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
    by_cluster: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "self_cited": 0}
    )
    for log_ in logs:
        c = qmap.get(log_.query_id, "unknown")
        by_cluster[c]["total"] += 1
        if log_.self_cited:
            by_cluster[c]["self_cited"] += 1
    return {
        c: {
            "total": v["total"],
            "self_cited": v["self_cited"],
            "rate": round(v["self_cited"] / v["total"], 3) if v["total"] else 0,
        }
        for c, v in by_cluster.items()
    }


async def run_strategic_review(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    end = date.today()
    start = end - timedelta(days=30)

    bc = tenant.business_context or {}
    breakdown = await _cluster_breakdown(session, tenant_id, start, end)
    anomalies = await detect_anomalies(session, tenant_id)

    prompt = PROMPT.format(
        business_context=json.dumps(bc, ensure_ascii=False, indent=2),
        cluster_breakdown=json.dumps(breakdown, ensure_ascii=False),
        anomalies=json.dumps(
            [
                {"kind": a.kind, "detail": a.detail, "severity": a.severity}
                for a in anomalies
            ],
            ensure_ascii=False,
        ),
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.eeat_analysis
    )
    res = await provider.generate(
        system_prompt="あなたは事業実態を踏まえる戦略コンサルタントです。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=8000,
        temperature=0.3,
    )
    log.info(
        "strategic_review_done",
        tenant_id=str(tenant_id),
        tokens=res.usage.total_tokens,
    )
    return parse_json_object(res.text, log_label="strategic_review_json")
