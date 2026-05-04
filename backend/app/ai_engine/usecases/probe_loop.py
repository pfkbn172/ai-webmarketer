"""実証クエリループユースケース。

「業種特化」と「地域特化」のような戦略軸を AI に提案させ、それぞれで仮想的に
引用される確率を Gemini に推論させて比較する。実 API を 20 クエリも投げると
枠を消費するため、本ユースケースは「Gemini に評価のみ」を依頼する形にする。

出力例:
{
  "axis_a": {"label": "業種特化(製造業 AI)", "expected_self_citation_rate": 0.05,
             "reasoning": "..."},
  "axis_b": {"label": "地域 × IT/DX サポート", "expected_self_citation_rate": 0.45,
             "reasoning": "..."},
  "winner": "axis_b",
  "recommended_queries": [...]
}
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.json_parse import parse_json_object
from app.ai_engine.providers.factory import AIProviderFactory
from app.db.models.enums import AIUseCaseEnum
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


PROMPT = """あなたは中小企業向け SEO/LLMO の戦略コンサルタントです。
以下の事業者について、2 つの戦略軸を比較評価してください。

## 事業者プロフィール
- 名称: {tenant_name}
- 業種: {industry}
- 事業ステージ: {stage}
- 拠点地域: {geographic_base}
- 独自性: {unique_value}
- 主要サービス: {primary_offerings}

## 評価対象の 2 つの戦略軸
- 軸 A: 業種特化(例: 製造業 AI 導入、関西 製造業 DX)
- 軸 B: 地域 × IT/DX サポート(例: 平野区 IT DX サポート、天王寺区 DX 比較)

## 評価項目(各軸について)
1. AI 検索(ChatGPT/Claude/Gemini)での引用獲得期待値(0.0〜1.0)
2. 競合の強さ(weak/medium/strong)
3. 事業ステージ適合度(low/medium/high)
4. 推奨クエリ(各軸で 5 本ずつ)

## 出力フォーマット(JSON)
{{
  "axis_a": {{
    "label": "業種特化",
    "expected_self_citation_rate": 0.05,
    "competitive_strength": "strong",
    "stage_fit": "low",
    "reasoning": "...",
    "sample_queries": ["..."]
  }},
  "axis_b": {{
    "label": "地域 × IT/DX サポート",
    "expected_self_citation_rate": 0.45,
    "competitive_strength": "weak",
    "stage_fit": "high",
    "reasoning": "...",
    "sample_queries": ["..."]
  }},
  "winner": "axis_b",
  "winner_rationale": "理由"
}}

JSON のみ返す。
"""


async def compare_strategy_axes(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

    prompt = PROMPT.format(
        tenant_name=tenant.name,
        industry=tenant.industry or "(未設定)",
        stage=bc.get("stage", "(未設定)"),
        geographic_base=", ".join(bc.get("geographic_base", [])) or "(未設定)",
        unique_value=", ".join(bc.get("unique_value", [])) or "(未設定)",
        primary_offerings=", ".join(bc.get("primary_offerings", [])) or "(未設定)",
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.eeat_analysis
    )
    res = await provider.generate(
        system_prompt="あなたは事業文脈を踏まえた戦略思考のプロです。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=4000,
        temperature=0.3,
    )
    log.info(
        "probe_loop_done", tenant_id=str(tenant_id), tokens=res.usage.total_tokens
    )
    return parse_json_object(res.text, log_label="probe_loop_json")
