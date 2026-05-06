"""今日の3アクションを生成する。

入力ソース:
  - keyword_universe(opportunity_flag付きのもの上位)
  - citation_opportunity(競合引用 > 0 / 自社引用 = 0)
  - business_context.strategic_review(最新のあれば)
  - last_brief_at, last_strategy_review_at, anomalies(将来的に拡張)

出力:
  - daily_actions テーブルに 3 行 upsert(同日重複は最新で置換)
  - 戻り値: 生成された DailyAction 3件のリスト
"""

import json
import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.ai_engine.usecases.citation_opportunity import find_opportunities
from app.db.models.content_brief import ContentBrief
from app.db.models.daily_action import DailyAction
from app.db.models.enums import AIUseCaseEnum
from app.db.models.keyword_universe import KeywordUniverse
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


OPPORTUNITY_LIMIT = 8
CITATION_OPP_LIMIT = 5


async def recommend_daily_actions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[DailyAction]:
    """今日のアクション3件を生成して保存し、返す。"""
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

    # 1) ユニバースの opportunity 上位
    opp_rows = list(
        (
            await session.scalars(
                select(KeywordUniverse)
                .where(
                    KeywordUniverse.tenant_id == tenant_id,
                    KeywordUniverse.opportunity_flag.in_(
                        ["high_demand_no_coverage", "near_top_3"]
                    ),
                )
                .order_by(desc(KeywordUniverse.priority_score))
                .limit(OPPORTUNITY_LIMIT)
            )
        ).all()
    )

    # 2) citation_opportunity(LLM 不要のロジカル抽出のみ流用)
    citation_opps = await find_opportunities(session, tenant_id, lookback_days=30)
    citation_opps = citation_opps[:CITATION_OPP_LIMIT]

    # 3) 直近のブリーフと戦略レビューの生成日
    last_brief = (
        await session.scalars(
            select(ContentBrief)
            .where(ContentBrief.tenant_id == tenant_id)
            .order_by(desc(ContentBrief.created_at))
            .limit(1)
        )
    ).one_or_none()
    last_brief_at = last_brief.created_at.isoformat() if last_brief else None

    sr_record = bc.get("strategic_review") if isinstance(bc, dict) else None
    last_strategy_review_at = None
    strategic_actions: list[str] = []
    if isinstance(sr_record, dict):
        last_strategy_review_at = sr_record.get("generated_at")
        result = sr_record.get("result") or {}
        if isinstance(result, dict):
            actions = result.get("recommended_actions") or result.get("actions") or []
            if isinstance(actions, list):
                strategic_actions = [str(a) for a in actions[:5]]

    prompt = render(
        "daily_action.md",
        {
            "tenant_name": tenant.name,
            "industry": tenant.industry or "(未設定)",
            "domain": tenant.domain,
            "geographic_base": ", ".join(bc.get("geographic_base", []) or []) or "(未設定)",
            "primary_offerings": ", ".join(bc.get("primary_offerings", []) or []) or "(未設定)",
            "opportunities": [_serialize_opp(r) for r in opp_rows],
            "citation_opportunities": citation_opps,
            "strategic_actions": strategic_actions,
            "anomalies": [],  # 将来 anomaly_detector の出力を集約
            "last_brief_at": last_brief_at,
            "last_strategy_review_at": last_strategy_review_at,
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.theme_suggestion  # 専用エナム未追加なので軽量用途を流用
    )
    res = await provider.generate(
        system_prompt="あなたは中小企業向け SEO/LLMO のシニア戦略家です。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=3500,
        temperature=0.3,
    )

    parsed = _parse_array(res.text)
    if not parsed:
        log.warning("daily_action_invalid_json", raw=res.text[:200])
        # 失敗時は前日のものをそのまま使う(返り値として現存DBの最新3件)
        return await _load_latest(session, tenant_id)

    # 同日生成済みは置換(最新で上書き)
    today = datetime.now(UTC)
    await session.execute(
        delete(DailyAction)
        .where(
            DailyAction.tenant_id == tenant_id,
            DailyAction.generated_at >= datetime(today.year, today.month, today.day, tzinfo=UTC),
        )
    )

    actions: list[DailyAction] = []
    for i, item in enumerate(parsed[:3], start=1):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        severity = (item.get("severity") or "yellow").strip().lower()
        if severity not in ("red", "yellow", "green"):
            severity = "yellow"
        if not title:
            continue
        a = DailyAction(
            tenant_id=tenant_id,
            generated_at=today,
            action_index=int(item.get("action_index") or i),
            title=title,
            severity=severity,
            rationale=item.get("rationale"),
            target_url=item.get("target_url"),
            related_keyword=item.get("related_keyword"),
        )
        session.add(a)
        actions.append(a)

    await session.commit()
    for a in actions:
        await session.refresh(a)
    log.info(
        "daily_action_done",
        tenant_id=str(tenant_id),
        count=len(actions),
        tokens=res.usage.total_tokens,
    )
    return actions


async def _load_latest(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[DailyAction]:
    return list(
        (
            await session.scalars(
                select(DailyAction)
                .where(DailyAction.tenant_id == tenant_id)
                .order_by(desc(DailyAction.generated_at), DailyAction.action_index)
                .limit(3)
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _serialize_opp(r: KeywordUniverse) -> dict[str, Any]:
    return {
        "keyword": r.keyword,
        "opportunity_flag": r.opportunity_flag,
        "priority_score": float(r.priority_score),
        "gsc_imp_12m": int(r.gsc_imp_12m),
        "gsc_avg_position": float(r.gsc_avg_position) if r.gsc_avg_position is not None else None,
        "suggest_derivative_count": int(r.suggest_derivative_count),
        "competitor_coverage_count": int(r.competitor_coverage_count),
    }


_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _parse_array(text: str) -> list:
    if not text:
        return []
    # 素直に
    try:
        v = json.loads(text)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    # コードフェンス内
    m = _FENCE_RE.search(text)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, list):
                return v
        except json.JSONDecodeError:
            pass
    # 最初の [ から最後の ]
    s = text.find("[")
    e = text.rfind("]")
    if s != -1 and e > s:
        try:
            v = json.loads(text[s : e + 1])
            if isinstance(v, list):
                return v
        except json.JSONDecodeError:
            pass
    return []
