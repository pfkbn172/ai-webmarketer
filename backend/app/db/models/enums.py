"""DB の PostgreSQL ENUM 型を Python 側でも定義。

implementation_plan.md 2.1 と完全に一致させること。
追加・変更時は Alembic マイグレーションで CREATE TYPE ... ADD VALUE が必要。
"""

import enum


class UserRoleEnum(enum.StrEnum):
    admin = "admin"
    client = "client"


class ComplianceTypeEnum(enum.StrEnum):
    general = "general"
    lawyer = "lawyer"
    medical = "medical"
    realestate = "realestate"
    finance = "finance"


class ContentStatusEnum(enum.StrEnum):
    draft = "draft"
    ai_generating = "ai_generating"
    review = "review"
    published = "published"
    archived = "archived"


class InquirySourceEnum(enum.StrEnum):
    web = "web"
    email = "email"
    phone = "phone"
    ai = "ai"
    other = "other"


class AiOriginEnum(enum.StrEnum):
    chatgpt = "chatgpt"
    claude = "claude"
    perplexity = "perplexity"
    gemini = "gemini"
    aio = "aio"


class InquiryStatusEnum(enum.StrEnum):
    new = "new"
    in_progress = "in_progress"
    contracted = "contracted"
    lost = "lost"


class LLMProviderEnum(enum.StrEnum):
    chatgpt = "chatgpt"
    claude = "claude"
    perplexity = "perplexity"
    gemini = "gemini"
    aio = "aio"


class AIUseCaseEnum(enum.StrEnum):
    monthly_report = "monthly_report"
    weekly_summary = "weekly_summary"
    theme_suggestion = "theme_suggestion"
    content_draft = "content_draft"
    compliance_check = "compliance_check"
    inquiry_structuring = "inquiry_structuring"
    eeat_analysis = "eeat_analysis"
    citation_opportunity = "citation_opportunity"


class AIProviderEnum(enum.StrEnum):
    gemini = "gemini"
    claude = "claude"
    openai = "openai"
    perplexity = "perplexity"


class CredentialProviderEnum(enum.StrEnum):
    gsc = "gsc"
    ga4 = "ga4"
    wordpress = "wordpress"
    resend = "resend"
    serpapi = "serpapi"
    gemini_ai_engine = "gemini_ai_engine"
    gemini_citation_monitor = "gemini_citation_monitor"
    openai = "openai"
    anthropic = "anthropic"
    perplexity = "perplexity"
    facebook = "facebook"


class JobStatusEnum(enum.StrEnum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class MarketingActionCategoryEnum(enum.StrEnum):
    """施策タイムライン用のカテゴリ。グラフ上のマーカーやレポート用の集計に使う。"""

    content_publish = "content_publish"  # 記事公開
    seo_optimize = "seo_optimize"  # SEO 改善・リライト
    ad_campaign = "ad_campaign"  # 広告
    pr = "pr"  # プレス・露出
    event = "event"  # イベント・登壇
    other = "other"
