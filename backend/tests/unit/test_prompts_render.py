"""全プロンプトテンプレートが Jinja2 でロード・レンダリングできることを確認。"""

from app.ai_engine.template_loader import render


def test_monthly_report_renders() -> None:
    out = render(
        "monthly_report.md",
        {
            "tenant_name": "kiseeeen",
            "period": "2026-04",
            "kpi_summary": "[]",
            "citation_trend": "x",
            "citation_opportunities": "",
            "schema_coverage": "",
            "contents": "[]",
            "inquiries_summary": "",
        },
    )
    assert "kiseeeen" in out
    assert "2026-04" in out


def test_theme_suggestion_renders() -> None:
    out = render(
        "theme_suggestion.md",
        {
            "tenant_name": "kiseeeen",
            "industry": "SaaS",
            "domain": "kiseeeen.co.jp",
            "missed_queries": ["q1", "q2"],
            "author_profile": "(none)",
        },
    )
    assert "q1" in out and "q2" in out


def test_inquiry_structuring_renders() -> None:
    out = render(
        "inquiry_structuring.md",
        {"raw_text": "御社のサービスに興味あり", "source_hint": "utm_source=chatgpt"},
    )
    assert "utm_source=chatgpt" in out


def test_compliance_check_renders() -> None:
    out = render(
        "compliance_check.md",
        {
            "industry": "lawyer",
            "compliance_rules": ["勝訴を保証する表現は不可"],
            "draft_text": "弊社は勝訴を保証します",
        },
    )
    assert "lawyer" in out
    assert "勝訴を保証する" in out


def test_eeat_renders() -> None:
    out = render(
        "eeat_analysis.md",
        {
            "tenant_name": "x",
            "author_profile": "プロフィール",
            "recent_contents": "[]",
        },
    )
    assert "プロフィール" in out


def test_citation_opportunity_renders() -> None:
    out = render(
        "citation_opportunity.md",
        {
            "tenant_name": "x",
            "domain": "x.co.jp",
            "opportunities": [
                {"query": "q1", "competitor_examples": ["a.com"]}
            ],
        },
    )
    assert "q1" in out and "a.com" in out


def test_content_draft_renders() -> None:
    out = render(
        "content_draft.md",
        {
            "title": "T",
            "target_query": "TQ",
            "outline": ["h1", "h2"],
            "tenant_name": "X",
            "industry": "law",
            "author_profile": "P",
            "compliance_rules": ["foo"],
        },
    )
    assert "TQ" in out and "foo" in out
