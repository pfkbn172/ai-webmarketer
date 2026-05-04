"""アラートルール評価サービス。

business_context.alert_rules に保存されたしきい値を週次で評価し、
超過したものをメール / Slack に通知する。
"""

import json
import urllib.request
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.citation_log import CitationLog
from app.db.models.inquiry import Inquiry
from app.db.models.kpi_log import KpiLog
from app.db.models.tenant import Tenant
from app.services import resend_mailer
from app.utils.logger import get_logger

log = get_logger(__name__)


async def evaluate_and_notify(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """テナントの全 alert_rules を評価して通知。発火件数を返す。"""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one_or_none()
    if tenant is None:
        return 0
    bc = tenant.business_context or {}
    rules: list[dict[str, Any]] = bc.get("alert_rules") or []
    if not rules:
        return 0

    fired = 0
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        try:
            if await _evaluate_rule(session, tenant_id, rule):
                _notify(rule, tenant_id)
                fired += 1
        except Exception:
            log.exception("alert_rule_eval_failed", rule=rule)
    return fired


async def _evaluate_rule(
    session: AsyncSession, tenant_id: uuid.UUID, rule: dict
) -> bool:
    metric = rule.get("metric")
    threshold = float(rule.get("threshold") or 0)
    today = date.today()

    if metric == "sessions_drop_pct":
        # 直近 7 日 vs その前 7 日のセッションが threshold% 以上落ちたら発火
        recent = (
            await session.scalar(
                select(func.coalesce(func.sum(KpiLog.sessions), 0)).where(
                    KpiLog.tenant_id == tenant_id,
                    KpiLog.date.between(today - timedelta(days=7), today - timedelta(days=1)),
                )
            )
            or 0
        )
        prev = (
            await session.scalar(
                select(func.coalesce(func.sum(KpiLog.sessions), 0)).where(
                    KpiLog.tenant_id == tenant_id,
                    KpiLog.date.between(
                        today - timedelta(days=14), today - timedelta(days=8)
                    ),
                )
            )
            or 0
        )
        if prev <= 0:
            return False
        drop = (prev - recent) / prev * 100
        return drop >= threshold

    if metric == "citations_drop_pct":
        recent = (
            await session.scalar(
                select(func.count(CitationLog.id)).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.self_cited.is_(True),
                    CitationLog.query_date.between(
                        today - timedelta(days=7), today - timedelta(days=1)
                    ),
                )
            )
            or 0
        )
        prev = (
            await session.scalar(
                select(func.count(CitationLog.id)).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.self_cited.is_(True),
                    CitationLog.query_date.between(
                        today - timedelta(days=14), today - timedelta(days=8)
                    ),
                )
            )
            or 0
        )
        if prev <= 0:
            return False
        drop = (prev - recent) / prev * 100
        return drop >= threshold

    if metric == "inquiries_zero_days":
        # 直近 N 日問い合わせが 0 件なら発火
        n = int(threshold)
        if n <= 0:
            return False
        cnt = (
            await session.scalar(
                select(func.count(Inquiry.id)).where(
                    Inquiry.tenant_id == tenant_id,
                    func.date(Inquiry.received_at).between(
                        today - timedelta(days=n), today - timedelta(days=1)
                    ),
                )
            )
            or 0
        )
        return cnt == 0

    return False


def _notify(rule: dict, tenant_id: uuid.UUID) -> None:
    metric = rule.get("metric") or "unknown"
    threshold = rule.get("threshold")
    subject = f"[AIウェブマーケター] アラート: {metric}"
    body = (
        f"<p>テナント {tenant_id} のアラートルール「{metric}」(しきい値: {threshold})が発火しました。</p>"
        f"<p>ダッシュボードで詳細を確認してください。</p>"
    )
    email = rule.get("notify_email")
    if email:
        try:
            resend_mailer.send(to=email, subject=subject, html=body)
        except Exception:
            log.exception("alert_email_failed", to=email)
    webhook = rule.get("notify_slack_webhook")
    if webhook:
        try:
            payload = json.dumps(
                {"text": f"⚠ {subject}\nしきい値: {threshold}, テナント: {tenant_id}"}
            ).encode("utf-8")
            req = urllib.request.Request(
                webhook, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except Exception:
            log.exception("alert_slack_failed")
