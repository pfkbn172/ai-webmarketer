"""コンテンツブリーフ生成ユースケース。

採用された keyword_universe レコード群を入力に、AI(Gemini)に
title/meta/h2_outline/related_keywords を JSON で出力させる。
結果は content_briefs テーブルに保存し、フロントから WordPress 下書きに連携可能。
"""

import json
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.author_profile import AuthorProfile
from app.db.models.competitor_post import CompetitorPost
from app.db.models.content_brief import ContentBrief
from app.db.models.enums import AIUseCaseEnum
from app.db.models.keyword_universe import KeywordUniverse
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


COMPETITOR_TITLE_LIMIT = 12  # プロンプトに渡す競合タイトル数の上限


async def generate_brief(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    primary_keyword: str,
    related_keyword_ids: list[uuid.UUID],
) -> ContentBrief:
    """primary_keyword + related_keyword_ids[] からブリーフを生成し DB 保存して返す。"""
    if not primary_keyword.strip():
        raise ValueError("primary_keyword is required")

    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

    # 主軸キーワードに該当する universe レコードを引く(無くても進む)
    primary_row = (
        await session.scalars(
            select(KeywordUniverse).where(
                KeywordUniverse.tenant_id == tenant_id,
                KeywordUniverse.keyword == primary_keyword.strip(),
            )
        )
    ).one_or_none()

    related_rows: list[KeywordUniverse] = []
    if related_keyword_ids:
        related_rows = list(
            (
                await session.scalars(
                    select(KeywordUniverse).where(
                        KeywordUniverse.tenant_id == tenant_id,
                        KeywordUniverse.id.in_(related_keyword_ids),
                    )
                )
            ).all()
        )

    selected: list[KeywordUniverse] = []
    if primary_row:
        selected.append(primary_row)
    selected.extend(r for r in related_rows if r.id != (primary_row.id if primary_row else None))

    primary_author = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id,
                AuthorProfile.is_primary.is_(True),
            )
        )
    ).one_or_none()
    author_text = (
        f"{primary_author.name}({primary_author.job_title or ''})"
        if primary_author
        else "(未登録)"
    )

    # 競合タイトル抜粋(プロンプトに渡す)
    competitor_titles = list(
        (
            await session.scalars(
                select(CompetitorPost.title)
                .where(CompetitorPost.tenant_id == tenant_id)
                .order_by(CompetitorPost.created_at.desc())
                .limit(COMPETITOR_TITLE_LIMIT)
            )
        ).all()
    )

    prompt = render(
        "content_brief.md",
        {
            "tenant_name": tenant.name,
            "industry": tenant.industry or "(未設定)",
            "domain": tenant.domain,
            "geographic_base": ", ".join(bc.get("geographic_base", [])) or "(未設定)",
            "primary_offerings": ", ".join(bc.get("primary_offerings", []))
            or "(未設定)",
            "author_profile": author_text,
            "primary_keyword": primary_keyword.strip(),
            "selected_keywords": [_serialize_kw(k) for k in selected],
            "competitor_titles": competitor_titles,
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.content_draft
    )
    res = await provider.generate(
        system_prompt="あなたは中小企業向け SEO/LLMO のシニア戦略家です。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=3000,
        temperature=0.4,
    )

    parsed = _parse_brief_json(res.text)
    if parsed is None:
        log.warning("content_brief_invalid_json", raw=res.text[:300])
        raise ValueError("LLM did not return valid JSON for content brief")

    title = (parsed.get("title") or "").strip()
    if not title:
        raise ValueError("LLM returned empty title")

    cluster_ids: list[str] = []
    for r in selected:
        for cid in r.cluster_ids or []:
            if cid not in cluster_ids:
                cluster_ids.append(cid)

    brief = ContentBrief(
        tenant_id=tenant_id,
        primary_keyword=primary_keyword.strip(),
        cluster_ids=cluster_ids,
        selected_keywords=[r.keyword for r in selected],
        title=title,
        meta_description=parsed.get("meta_description"),
        h2_outline=_normalize_h2(parsed.get("h2_outline") or []),
        related_keywords=parsed.get("related_keywords") or [],
        competitor_refs=[],  # Phase 5 では URL 連携は無し(Phase 3 で本格化予定)
        target_url_slug=parsed.get("target_url_slug"),
        rationale=parsed.get("rationale"),
        status="draft",
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)

    log.info(
        "content_brief_generated",
        tenant_id=str(tenant_id),
        brief_id=str(brief.id),
        h2_count=len(brief.h2_outline),
        related_count=len(brief.related_keywords),
        tokens=res.usage.total_tokens,
    )
    return brief


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _serialize_kw(r: KeywordUniverse) -> dict[str, Any]:
    return {
        "keyword": r.keyword,
        "cluster_ids": list(r.cluster_ids or []),
        "gsc_imp_12m": r.gsc_imp_12m,
        "gsc_avg_position": float(r.gsc_avg_position) if r.gsc_avg_position is not None else None,
        "suggest_derivative_count": r.suggest_derivative_count,
        "competitor_coverage_count": r.competitor_coverage_count,
        "llm_self_cite_rate": float(r.llm_self_cite_rate) if r.llm_self_cite_rate is not None else None,
        "opportunity_flag": r.opportunity_flag,
    }


_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _parse_brief_json(text: str) -> dict | None:
    """コードフェンスや前後説明があっても JSON オブジェクトを取り出す。"""
    if not text:
        return None
    # まず素直に
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    # ```json ... ``` フェンス内
    m = _FENCE_RE.search(text)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    # 最初の { から最後の } まで
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e > s:
        try:
            v = json.loads(text[s : e + 1])
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    return None


def _normalize_h2(raw: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        h2 = (item.get("h2") or "").strip()
        if not h2:
            continue
        target = item.get("target_keywords") or []
        if not isinstance(target, list):
            target = []
        rationale = item.get("rationale")
        out.append(
            {
                "h2": h2,
                "target_keywords": [str(t) for t in target if str(t).strip()],
                "rationale": str(rationale) if rationale else None,
            }
        )
    return out
