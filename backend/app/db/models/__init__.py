"""ORM モデル登録。

alembic/env.py から `from app.db import models` で参照され、
ここに import された全モデルが Base.metadata に登録される。

新しいモデルを追加したら必ずこのファイルに import を追加すること。
"""

from app.db.models.ai_provider_config import AIProviderConfig
from app.db.models.audit_log import AuditLog
from app.db.models.author_profile import AuthorProfile
from app.db.models.citation_log import CitationLog
from app.db.models.competitor import Competitor
from app.db.models.competitor_post import CompetitorPost
from app.db.models.content import Content
from app.db.models.content_metric import ContentMetric
from app.db.models.enums import (
    AiOriginEnum,
    AIProviderEnum,
    AIUseCaseEnum,
    ComplianceTypeEnum,
    ContentStatusEnum,
    CredentialProviderEnum,
    InquirySourceEnum,
    InquiryStatusEnum,
    JobStatusEnum,
    LLMProviderEnum,
    UserRoleEnum,
)
from app.db.models.ga4_ai_referral_daily import Ga4AiReferralDaily
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.ga4_page_daily import Ga4PageDaily
from app.db.models.gsc_page_metric import GscPageMetric
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.inquiry import Inquiry
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.kpi_log import KpiLog
from app.db.models.marketing_action import MarketingAction
from app.db.models.prompt_template import PromptTemplate
from app.db.models.report import Report
from app.db.models.schema_audit_log import SchemaAuditLog
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.db.models.tenant_credential import TenantCredential
from app.db.models.user import User
from app.db.models.user_tenant import UserTenant

__all__ = [
    "AIProviderConfig",
    "AIProviderEnum",
    "AIUseCaseEnum",
    "AiOriginEnum",
    "AuditLog",
    "AuthorProfile",
    "CitationLog",
    "Competitor",
    "CompetitorPost",
    "ComplianceTypeEnum",
    "Content",
    "ContentMetric",
    "Ga4AiReferralDaily",
    "Ga4DailyMetric",
    "Ga4PageDaily",
    "GscPageMetric",
    "GscQueryMetric",
    "ContentStatusEnum",
    "CredentialProviderEnum",
    "Inquiry",
    "InquirySourceEnum",
    "InquiryStatusEnum",
    "JobExecutionLog",
    "JobStatusEnum",
    "KpiLog",
    "LLMProviderEnum",
    "MarketingAction",
    "PromptTemplate",
    "Report",
    "SchemaAuditLog",
    "TargetQuery",
    "Tenant",
    "TenantCredential",
    "User",
    "UserRoleEnum",
    "UserTenant",
]
