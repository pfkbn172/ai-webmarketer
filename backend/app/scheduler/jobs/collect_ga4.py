"""GA4 週次収集ジョブ。"""

from sqlalchemy import select, text

from app.collectors.ga4.runner import run_for_tenant
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.encryption import decrypt_json
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
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
                        TenantCredential.provider == CredentialProviderEnum.ga4,
                    )
                )
            ).one_or_none()
            if cred is None:
                log.info("ga4_skip_no_cred", tenant_id=str(tenant_id))
                continue
            payload = decrypt_json(cred.encrypted_data)
            property_id = payload.get("property_id")
            if not property_id:
                log.warning("ga4_skip_no_property_id", tenant_id=str(tenant_id))
                continue
            try:
                await run_for_tenant(session, tenant_id, property_id=property_id, days=7)
            except Exception:
                log.exception("ga4_job_failed", tenant_id=str(tenant_id))
