"""schema_injector の build_* が正しい JSON-LD を生成することを確認。"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.services.schema_injector import (
    build_article_schema,
    build_breadcrumb_schema,
    build_faq_schema,
    build_organization_schema,
    build_person_schema,
)


def test_build_organization_schema() -> None:
    tenant = MagicMock(name="kiseeeen", domain="kiseeeen.co.jp")
    tenant.name = "kiseeeen"
    tenant.domain = "kiseeeen.co.jp"
    s = build_organization_schema(tenant)
    assert s["@type"] == "Organization"
    assert s["name"] == "kiseeeen"
    assert s["url"].startswith("https://kiseeeen.co.jp")


def test_build_person_schema_with_minimal_fields() -> None:
    author = MagicMock()
    author.name = "黄瀬剛志"
    author.job_title = "代表取締役"
    author.works_for = "株式会社kiseeeen"
    author.alumni_of = []
    author.credentials = []
    author.bio_short = "短い経歴"
    author.social_profiles = ["https://x.com/foo"]
    s = build_person_schema(author)
    assert s["@type"] == "Person"
    assert s["name"] == "黄瀬剛志"
    assert s["jobTitle"] == "代表取締役"
    assert s["sameAs"] == ["https://x.com/foo"]


def test_build_article_schema() -> None:
    tenant = MagicMock()
    tenant.name = "kiseeeen"
    tenant.domain = "kiseeeen.co.jp"
    content = MagicMock()
    content.title = "AIウェブマーケターとは"
    content.url = "https://kiseeeen.co.jp/posts/1"
    content.published_at = datetime(2026, 5, 1, tzinfo=UTC)
    content.updated_at = datetime(2026, 5, 1, tzinfo=UTC)
    s = build_article_schema(tenant=tenant, content=content, author=None)
    assert s["@type"] == "Article"
    assert s["headline"] == "AIウェブマーケターとは"
    assert "publisher" in s


def test_build_faq_schema() -> None:
    s = build_faq_schema(
        [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]
    )
    assert s["@type"] == "FAQPage"
    assert len(s["mainEntity"]) == 2
    assert s["mainEntity"][0]["acceptedAnswer"]["text"] == "A1"


def test_build_breadcrumb_schema() -> None:
    s = build_breadcrumb_schema(
        [
            {"name": "Home", "url": "https://x.com/"},
            {"name": "Blog", "url": "https://x.com/blog"},
        ]
    )
    assert s["itemListElement"][0]["position"] == 1
    assert s["itemListElement"][1]["item"] == "https://x.com/blog"
