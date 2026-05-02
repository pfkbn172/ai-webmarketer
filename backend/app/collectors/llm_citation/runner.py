"""AI 引用モニタジョブのランナー。

各テナントについて、ターゲットクエリ × 主要 5 LLM(ChatGPT/Claude/Perplexity/Gemini/AIO)
で回答を取得し、文字列マッチ判定して citation_logs に保存する。
"""

import asyncio
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.llm_citation._types import CitationProbeResult
from app.collectors.llm_citation.aio_client import AIOverviewsCitationClient
from app.collectors.llm_citation.chatgpt_client import ChatGPTCitationClient
from app.collectors.llm_citation.claude_client import ClaudeCitationClient
from app.collectors.llm_citation.gemini_client import GeminiCitationClient
from app.collectors.llm_citation.matcher import MatchProfile, evaluate
from app.collectors.llm_citation.perplexity_client import PerplexityCitationClient
from app.db.models.citation_log import CitationLog
from app.db.models.competitor import Competitor
from app.db.models.enums import (
    CredentialProviderEnum,
    JobStatusEnum,
    LLMProviderEnum,
)
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "monitor_citation"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    self_aliases: list[str] | None = None,
) -> int:
    """指定テナントのターゲットクエリ全件 × 主要 4 LLM で引用モニタを実行。

    Returns:
        作成した citation_logs の行数
    """
    started = datetime.now(UTC)
    job_log = JobExecutionLog(
        tenant_id=tenant_id,
        job_name=JOB_NAME,
        status=JobStatusEnum.running,
        started_at=started,
    )
    session.add(job_log)
    await session.flush()

    try:
        # RLS のため app.tenant_id を設定
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        # テナント情報 + クエリ + 競合
        tenant = (
            await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
        ).one()
        queries = list(
            (
                await session.scalars(
                    select(TargetQuery).where(TargetQuery.is_active.is_(True))
                )
            ).all()
        )
        competitors = list(
            (
                await session.scalars(
                    select(Competitor).where(Competitor.is_active.is_(True))
                )
            ).all()
        )

        if not queries:
            job_log.status = JobStatusEnum.skipped
            job_log.error_text = "no active target queries"
            job_log.finished_at = datetime.now(UTC)
            await session.commit()
            log.warning("citation_monitor_no_queries", tenant_id=str(tenant_id))
            return 0

        profile = MatchProfile(
            self_domain=tenant.domain,
            self_aliases=[tenant.name, *(self_aliases or [])],
            competitor_domains=[c.domain for c in competitors],
        )

        # 各 LLM クライアントを構築(認証情報が無い LLM はスキップ)
        clients = await _build_clients(session, tenant_id)
        if not clients:
            job_log.status = JobStatusEnum.skipped
            job_log.error_text = "no LLM credentials configured"
            job_log.finished_at = datetime.now(UTC)
            await session.commit()
            log.warning("citation_monitor_no_clients", tenant_id=str(tenant_id))
            return 0

        # クエリ × LLM の組合せを実行
        today = date.today()
        rows_created = 0
        for q in queries:
            for llm, client in clients.items():
                try:
                    result = await client.probe(q.query_text)
                except Exception as exc:
                    log.warning(
                        "citation_probe_failed",
                        llm=llm.value,
                        query=q.query_text[:60],
                        error=str(exc),
                    )
                    continue
                rows_created += await _save_result(
                    session, tenant_id, q.id, today, result, profile
                )
                # API レート制御の保険
                await asyncio.sleep(0.5)
        await session.commit()

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        job_log.job_metadata = {
            "queries": len(queries),
            "llms": [k.value for k in clients],
            "logs_written": rows_created,
        }
        await session.commit()
        log.info(
            "citation_monitor_done",
            tenant_id=str(tenant_id),
            rows=rows_created,
        )
        return rows_created

    except Exception as exc:
        job_log.status = JobStatusEnum.failed
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = f"{type(exc).__name__}: {exc}"
        await session.commit()
        log.exception("citation_monitor_failed", tenant_id=str(tenant_id))
        raise


async def _resolve_api_key(
    repo: TenantCredentialRepository,
    tenant_id: uuid.UUID,
    cred_provider: CredentialProviderEnum,
    env_attr: str,
) -> str | None:
    """tenant_credentials を最優先、なければ .env(settings)を見る。

    本来は scripts/register_llm_credentials.py で .env → tenant_credentials に
    コピー登録するのが推奨だが、開発・初期動作確認では .env だけでも
    引用モニタが回るようフォールバックする。
    """
    from app.settings import settings

    cred = await repo.get_decrypted(tenant_id, cred_provider)
    if cred and cred.get("api_key"):
        return cred["api_key"]
    return getattr(settings, env_attr, None) or None


async def _build_clients(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict[LLMProviderEnum, object]:
    """tenant_credentials または .env の API キーから LLM クライアントを生成。"""
    repo = TenantCredentialRepository(session)
    clients: dict[LLMProviderEnum, object] = {}

    if key := await _resolve_api_key(
        repo, tenant_id, CredentialProviderEnum.openai, "openai_api_key"
    ):
        clients[LLMProviderEnum.chatgpt] = ChatGPTCitationClient(key)

    if key := await _resolve_api_key(
        repo, tenant_id, CredentialProviderEnum.anthropic, "anthropic_api_key"
    ):
        clients[LLMProviderEnum.claude] = ClaudeCitationClient(key)

    if key := await _resolve_api_key(
        repo, tenant_id, CredentialProviderEnum.perplexity, "perplexity_api_key"
    ):
        clients[LLMProviderEnum.perplexity] = PerplexityCitationClient(key)

    if key := await _resolve_api_key(
        repo,
        tenant_id,
        CredentialProviderEnum.gemini_citation_monitor,
        "gemini_api_key_citation_monitor",
    ):
        clients[LLMProviderEnum.gemini] = GeminiCitationClient(key)

    if key := await _resolve_api_key(
        repo, tenant_id, CredentialProviderEnum.serpapi, "serpapi_key"
    ):
        clients[LLMProviderEnum.aio] = AIOverviewsCitationClient(key)

    return clients


async def _save_result(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query_id: uuid.UUID,
    today: date,
    result: CitationProbeResult,
    profile: MatchProfile,
) -> int:
    match = evaluate(result.response_text, result.cited_urls, profile)
    log_row = CitationLog(
        tenant_id=tenant_id,
        query_id=query_id,
        llm_provider=result.llm_provider,
        query_date=today,
        response_text=result.response_text,
        cited_urls=result.cited_urls,
        self_cited=match.self_cited,
        competitor_cited=match.competitor_cited,
        raw_response=result.raw_response,
    )
    session.add(log_row)
    await session.flush()
    return 1
