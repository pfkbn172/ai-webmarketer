"""クエリ提案ユースケース。

business_context を踏まえて Gemini に「現実的に勝てるクエリ 15〜20 本」を
提案させる。Phase 2 戦略思考レイヤーの中核。
"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.enums import AIUseCaseEnum
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def suggest_queries(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[dict]:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

    existing = list(
        (
            await session.scalars(
                select(TargetQuery).where(
                    TargetQuery.tenant_id == tenant_id,
                    TargetQuery.is_active.is_(True),
                )
            )
        ).all()
    )

    prompt = render(
        "query_suggestion.md",
        {
            "tenant_name": tenant.name,
            "industry": tenant.industry or "(未設定)",
            "domain": tenant.domain,
            "stage": bc.get("stage", "(未設定)"),
            "geographic_base": ", ".join(bc.get("geographic_base", [])) or "(未設定)",
            "geographic_expansion": ", ".join(bc.get("geographic_expansion", []))
            or "(未設定)",
            "unique_value": ", ".join(bc.get("unique_value", [])) or "(未設定)",
            "primary_offerings": ", ".join(bc.get("primary_offerings", []))
            or "(未設定)",
            "target_customer": bc.get("target_customer", "(未設定)"),
            "weak_segments": ", ".join(bc.get("weak_segments", [])) or "(なし)",
            "strong_segments": ", ".join(bc.get("strong_segments", [])) or "(なし)",
            "existing_queries": [q.query_text for q in existing],
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.theme_suggestion
    )
    res = await provider.generate(
        system_prompt="あなたは中小企業向け SEO/LLMO 戦略コンサルタントです。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=8000,
        temperature=0.5,
    )
    log.info(
        "query_suggestion_done",
        tenant_id=str(tenant_id),
        tokens=res.usage.total_tokens,
    )
    return _parse_json_array(res.text)


def _parse_json_array(text: str) -> list[dict]:
    """JSON 配列を抽出する。コードフェンスや前後説明が混入しても拾えるよう、
    最初の '[' から最後の ']' までを抽出してパースする。出力が途中で切れた場合は
    末尾の不完全なオブジェクトを切り捨てて再パースする。
    """
    if not text:
        return []
    # 最初の [ から最後の ] までを抽出
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        log.warning("query_suggestion_no_array", raw=text[:200])
        return []
    snippet = text[start : end + 1]
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        # 出力が途中で切れた場合: 完成しているオブジェクトだけ残す
        # "}, " を区切りに探して最後の閉じ ", " 位置で配列を閉じ直す
        last_close = snippet.rfind("},")
        if last_close > 0:
            patched = snippet[: last_close + 1] + "]"
            try:
                parsed = json.loads(patched)
                if isinstance(parsed, list):
                    log.info("query_suggestion_partial_recovered", n=len(parsed))
                    return parsed
            except json.JSONDecodeError:
                pass
    log.warning("query_suggestion_invalid_json", raw=text[:200])
    return []
