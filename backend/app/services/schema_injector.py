"""JSON-LD 構造化データを生成するサービス(Article / FAQPage / Person / BreadcrumbList)。

仕様書 4.2.4 に従う。WordPress REST API への書き戻しは wordpress_publisher.py。
本モジュールは「組み立て」のみを責務とする(I/O なし)。
"""

from datetime import datetime
from typing import Any

from app.db.models.author_profile import AuthorProfile
from app.db.models.content import Content
from app.db.models.tenant import Tenant


def build_article_schema(
    *, tenant: Tenant, content: Content, author: AuthorProfile | None
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": content.title,
        "url": content.url,
        "datePublished": (content.published_at or datetime.utcnow()).isoformat(),
        "dateModified": content.updated_at.isoformat() if content.updated_at else None,
        "publisher": {
            "@type": "Organization",
            "name": tenant.name,
            "url": f"https://{tenant.domain}/",
        },
    }
    if author:
        schema["author"] = build_person_schema(author)
    return schema


def build_person_schema(author: AuthorProfile) -> dict[str, Any]:
    person: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": author.name,
    }
    if author.job_title:
        person["jobTitle"] = author.job_title
    if author.works_for:
        person["worksFor"] = {"@type": "Organization", "name": author.works_for}
    if author.alumni_of:
        person["alumniOf"] = author.alumni_of
    if author.credentials:
        person["hasCredential"] = author.credentials
    if author.bio_short:
        person["description"] = author.bio_short
    if author.social_profiles:
        person["sameAs"] = author.social_profiles
    return person


def build_faq_schema(faqs: list[dict[str, str]]) -> dict[str, Any]:
    """faqs: [{"question": "...", "answer": "..."}, ...]"""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["question"],
                "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
            }
            for f in faqs
        ],
    }


def build_organization_schema(tenant: Tenant) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": tenant.name,
        "url": f"https://{tenant.domain}/",
    }


def build_breadcrumb_schema(items: list[dict[str, str]]) -> dict[str, Any]:
    """items: [{"name": "Home", "url": "..."}, {"name": "Blog", "url": "..."}, ...]"""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": it["name"],
                "item": it["url"],
            }
            for i, it in enumerate(items)
        ],
    }
