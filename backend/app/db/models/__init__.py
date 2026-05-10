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
from app.db.models.content_brief import ContentBrief
from app.db.models.content_metric import ContentMetric
from app.db.models.daily_action import DailyAction
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
from app.db.models.gsc_page_metric import GscPageMetric
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.inquiry import Inquiry
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.keyword_suggestion import KeywordSuggestion
from app.db.models.keyword_universe import KeywordUniverse
from app.db.models.kpi_log import KpiLog
from app.db.models.marketing_action import MarketingAction
from app.db.models.page_speed_metric import PageSpeedMetric
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
    "ContentBrief",
    "ContentMetric",
    "DailyAction",
    "Ga4AiCrawlerDaily",
    "Ga4AiCrawlerPageDaily",
    "Ga4AiReferralDaily",
    "Ga4AiReferralEventDaily",
    "Ga4ArticleReadCompleteDaily",
    "Ga4CtaClickDaily",
    "Ga4DailyMetric",
    "Ga4EngagementSignalDaily",
    "Ga4HourlyMetric",
    "Ga4LlmsTxtFetchDaily",
    "Ga4OutboundClickDaily",
    "Ga4PageDaily",
    "Ga4ReferralDaily",
    "Ga4ReferralHourly",
    "Ga4TextCopyDaily",
    "Ga4ToolUseDaily",
    "GscPageMetric",
    "GscQueryMetric",
    "ContentStatusEnum",
    "CredentialProviderEnum",
    "Inquiry",
    "InquirySourceEnum",
    "InquiryStatusEnum",
    "JobExecutionLog",
    "JobStatusEnum",
    "KeywordSuggestion",
    "KeywordUniverse",
    "KpiLog",
    "LLMProviderEnum",
    "MarketingAction",
    "PageSpeedMetric",
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
