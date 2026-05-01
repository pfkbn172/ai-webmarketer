"""GSC 週次収集ジョブ。"""

from sqlalchemy import select, text

from app.collectors.gsc.runner import run_for_tenant
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    """全アクティブテナントに対して GSC 収集を実行。

    site_url は tenant_credentials.gsc.payload.site_url から取得する想定
    (google_oauth_setup.py で保管時に site_url も含める)。
    無ければ "sc-domain:<tenant.domain>" にフォールバック。
    """
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            cred = (
                await session.scalars(
                    select(TenantCredential).where(
                        TenantCredential.tenant_id == tenant_id,
                        TenantCredential.provider == CredentialProviderEnum.gsc,
                    )
                )
            ).one_or_none()
            if cred is None:
                log.info("gsc_skip_no_cred", tenant_id=str(tenant_id))
                continue
            from app.utils.encryption import decrypt_json
            payload = decrypt_json(cred.encrypted_data)
            site_url = payload.get("site_url") or f"sc-domain:{payload.get('domain', '')}"
            try:
                await run_for_tenant(session, tenant_id, site_url=site_url, days=7)
            except Exception:
                log.exception("gsc_job_failed", tenant_id=str(tenant_id))
