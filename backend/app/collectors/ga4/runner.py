"""GA4 収集ジョブのランナー。GSC ランナーと同じパターン。"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.ga4.client import Ga4Client
from app.collectors.google_oauth import (
    CredentialsNotFoundError,
    load_google_credentials,
)
from app.db.models.enums import CredentialProviderEnum, JobStatusEnum
from app.db.models.ga4_ai_crawler_daily import Ga4AiCrawlerDaily
from app.db.models.ga4_ai_crawler_page_daily import Ga4AiCrawlerPageDaily
from app.db.models.ga4_ai_referral_daily import Ga4AiReferralDaily
from app.db.models.ga4_ai_referral_event_daily import Ga4AiReferralEventDaily
from app.db.models.ga4_article_read_complete_daily import Ga4ArticleReadCompleteDaily
from app.db.models.ga4_cta_click_daily import Ga4CtaClickDaily
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.ga4_engagement_signal_daily import Ga4EngagementSignalDaily
from app.db.models.ga4_hourly_metric import Ga4HourlyMetric
from app.db.models.ga4_llms_txt_fetch_daily import Ga4LlmsTxtFetchDaily
from app.db.models.ga4_outbound_click_daily import Ga4OutboundClickDaily
from app.db.models.ga4_page_daily import Ga4PageDaily
from app.db.models.ga4_referral_daily import Ga4ReferralDaily
from app.db.models.ga4_referral_hourly import Ga4ReferralHourly
from app.db.models.ga4_text_copy_daily import Ga4TextCopyDaily
from app.db.models.ga4_tool_use_daily import Ga4ToolUseDaily
from app.db.models.job_execution_log import JobExecutionLog
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_ga4"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    property_id: str,
    days: int = 7,
) -> int:
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
        repo = TenantCredentialRepository(session)
        creds = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.ga4)
        client = Ga4Client(creds, property_id=property_id)

        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        rows = await client.daily_metrics(start, end)
        ai_rows = await client.ai_referrals(start, end)
        page_rows = await client.page_metrics(start, end)
        hourly_rows = await client.hourly_metrics(start, end)
        ref_rows = await client.referrals_daily(start, end)
        ref_hourly_rows = await client.referrals_hourly(start, end)

        await _upsert_metrics(session, tenant_id, rows)
        await _upsert_ai_referrals(session, tenant_id, ai_rows)
        await _upsert_page_rows(session, tenant_id, page_rows)
        await _upsert_hourly_rows(session, tenant_id, hourly_rows)
        await _upsert_referral_daily(session, tenant_id, ref_rows)
        await _upsert_referral_hourly(session, tenant_id, ref_hourly_rows)

        # --- 2026-05 追加カスタムイベント -----------------------------------
        # 各メソッドは独立に try/except する。ディメンション伝播未完で 1 メソッド
        # が失敗しても、他のメトリクス収集は継続する。
        custom_counts: dict[str, int] = {}
        for key, fetcher, upserter in (
            ("ai_referral_event", client.ai_referral_events, _upsert_ai_referral_events),
            ("ai_crawler", client.ai_crawler_visits, _upsert_ai_crawler),
            ("ai_crawler_page", client.ai_crawler_pages, _upsert_ai_crawler_page),
            ("llms_txt_fetch", client.llms_txt_fetches, _upsert_llms_txt_fetch),
            ("article_read", client.article_read_completes, _upsert_article_read),
            ("text_copy", client.text_copy_events, _upsert_text_copy),
            ("outbound_click", client.outbound_click_events, _upsert_outbound_click),
            ("cta_click", client.cta_click_events, _upsert_cta_click),
            ("tool_use", client.tool_use_events, _upsert_tool_use),
            ("engagement_signal", client.engagement_signals, _upsert_engagement_signal),
        ):
            try:
                rs = await fetcher(start, end)
                await upserter(session, tenant_id, rs)
                custom_counts[key] = len(rs)
            except Exception as exc:
                custom_counts[key] = -1
                log.warning(
                    "ga4_collect_custom_failed",
                    tenant_id=str(tenant_id),
                    event_key=key,
                    error=f"{type(exc).__name__}: {exc}",
                )

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        job_log.job_metadata = {
            "row_count": len(rows),
            "ai_referral_rows": len(ai_rows),
            "page_rows": len(page_rows),
            "hourly_rows": len(hourly_rows),
            "referral_rows": len(ref_rows),
            "referral_hourly_rows": len(ref_hourly_rows),
            "custom_event_rows": custom_counts,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        await session.commit()
        log.info(
            "ga4_collect_done",
            tenant_id=str(tenant_id),
            rows=len(rows),
            ai_referral_rows=len(ai_rows),
            page_rows=len(page_rows),
        )
        return len(rows)

    except CredentialsNotFoundError as exc:
        job_log.status = JobStatusEnum.skipped
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = str(exc)
        await session.commit()
        log.warning("ga4_collect_skipped", tenant_id=str(tenant_id), reason=str(exc))
        return 0
    except Exception as exc:
        job_log.status = JobStatusEnum.failed
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = f"{type(exc).__name__}: {exc}"
        await session.commit()
        log.exception("ga4_collect_failed", tenant_id=str(tenant_id))
        raise


async def _upsert_metrics(session: AsyncSession, tenant_id: uuid.UUID, rows: list) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "sessions": r.sessions,
            "users": r.users,
            "bounce_rate": r.bounce_rate,
            "conversions": r.conversions,
            "organic_sessions": r.organic_sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4DailyMetric).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_daily_tenant_date",
        set_={
            "sessions": stmt.excluded.sessions,
            "users": stmt.excluded.users,
            "bounce_rate": stmt.excluded.bounce_rate,
            "conversions": stmt.excluded.conversions,
            "organic_sessions": stmt.excluded.organic_sessions,
        },
    )
    await session.execute(stmt)


async def _upsert_page_rows(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "page_path": r.page_path,
            "sessions": r.sessions,
            "users": r.users,
            "conversions": r.conversions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4PageDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_pd_tenant_date_path",
        set_={
            "sessions": stmt.excluded.sessions,
            "users": stmt.excluded.users,
            "conversions": stmt.excluded.conversions,
        },
    )
    await session.execute(stmt)


async def _upsert_hourly_rows(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "hour": r.hour,
            "sessions": r.sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4HourlyMetric).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_hourly_tenant_date_hour",
        set_={"sessions": stmt.excluded.sessions},
    )
    await session.execute(stmt)


async def _upsert_referral_daily(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "source": r.source,
            "medium": r.medium,
            "sessions": r.sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4ReferralDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_ref_d_tenant_date_src_med",
        set_={"sessions": stmt.excluded.sessions},
    )
    await session.execute(stmt)


async def _upsert_referral_hourly(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    # cardinality が大きく asyncpg の bind 変数上限(32767)に当たるため、
    # 5000 行ずつチャンクして INSERT する。
    CHUNK = 5000
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        payload = [
            {
                "tenant_id": tenant_id,
                "date": r.date,
                "hour": r.hour,
                "source": r.source,
                "medium": r.medium,
                "sessions": r.sessions,
            }
            for r in chunk
        ]
        stmt = pg_insert(Ga4ReferralHourly).values(payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_ref_h_tenant_date_hour_src_med",
            set_={"sessions": stmt.excluded.sessions},
        )
        await session.execute(stmt)


async def _upsert_ai_referrals(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "source_host": r.source_host,
            "sessions": r.sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4AiReferralDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_ai_ref_tenant_date_host",
        set_={"sessions": stmt.excluded.sessions},
    )
    await session.execute(stmt)


# --- 2026-05 追加カスタムイベント用 _upsert ヘルパー ----------------------------

# asyncpg bind 変数上限(32767)対策。高カーディナリティテーブル用。
_CUSTOM_CHUNK = 5000


async def _set_tenant_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def _upsert_ai_referral_events(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "ai_referrer_domain": r.ai_referrer_domain,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4AiReferralEventDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_ai_ref_evt_tenant_date_dom",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)


async def _upsert_ai_crawler(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "crawler_name": r.crawler_name,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4AiCrawlerDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_ai_crawl_tenant_date_name",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)


async def _upsert_ai_crawler_page(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    for i in range(0, len(rows), _CUSTOM_CHUNK):
        chunk = rows[i : i + _CUSTOM_CHUNK]
        payload = [
            {
                "tenant_id": tenant_id,
                "date": r.date,
                "crawler_name": r.crawler_name,
                "page_path": r.page_path,
                "event_count": r.event_count,
            }
            for r in chunk
        ]
        stmt = pg_insert(Ga4AiCrawlerPageDaily).values(payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_ai_crawl_pg_tenant_date_name_path",
            set_={"event_count": stmt.excluded.event_count},
        )
        await session.execute(stmt)


async def _upsert_llms_txt_fetch(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "crawler_name": r.crawler_name,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4LlmsTxtFetchDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_llms_tenant_date_name",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)


async def _upsert_article_read(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "page_path": r.page_path,
            "event_count": r.event_count,
            "page_views": r.page_views,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4ArticleReadCompleteDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_arc_tenant_date_path",
        set_={
            "event_count": stmt.excluded.event_count,
            "page_views": stmt.excluded.page_views,
        },
    )
    await session.execute(stmt)


async def _upsert_text_copy(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    for i in range(0, len(rows), _CUSTOM_CHUNK):
        chunk = rows[i : i + _CUSTOM_CHUNK]
        payload = [
            {
                "tenant_id": tenant_id,
                "date": r.date,
                "page_path": r.page_path,
                "content_type": r.content_type,
                "event_count": r.event_count,
            }
            for r in chunk
        ]
        stmt = pg_insert(Ga4TextCopyDaily).values(payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_txc_tenant_date_path_type",
            set_={"event_count": stmt.excluded.event_count},
        )
        await session.execute(stmt)


async def _upsert_outbound_click(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "outbound_category": r.outbound_category,
            "link_domain": r.link_domain,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4OutboundClickDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_outb_tenant_date_cat_dom",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)


async def _upsert_cta_click(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "lp_id": r.lp_id,
            "cta_id": r.cta_id,
            "event_count": r.event_count,
            "lp_sessions": r.lp_sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4CtaClickDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_cta_tenant_date_lp_cta",
        set_={
            "event_count": stmt.excluded.event_count,
            "lp_sessions": stmt.excluded.lp_sessions,
        },
    )
    await session.execute(stmt)


async def _upsert_tool_use(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "tool_name": r.tool_name,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4ToolUseDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_tool_tenant_date_name",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)


async def _upsert_engagement_signal(
    session: AsyncSession, tenant_id: uuid.UUID, rows: list
) -> None:
    if not rows:
        return
    await _set_tenant_ctx(session, tenant_id)
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "event_name": r.event_name,
            "sub_key": r.sub_key,
            "event_count": r.event_count,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4EngagementSignalDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_engsig_tenant_date_evt_sub",
        set_={"event_count": stmt.excluded.event_count},
    )
    await session.execute(stmt)
