from app.collectors.llm_citation.matcher import MatchProfile, evaluate


def _profile(
    *,
    domain: str = "kiseeeen.co.jp",
    aliases: list[str] | None = None,
    competitors: list[str] | None = None,
) -> MatchProfile:
    return MatchProfile(
        self_domain=domain,
        self_aliases=aliases or ["kiseeeen", "株式会社kiseeeen", "黄瀬剛志"],
        competitor_domains=competitors or ["competitor1.com", "competitor2.jp"],
    )


def test_self_cited_via_url() -> None:
    r = evaluate(
        "Some answer",
        cited_urls=["https://kiseeeen.co.jp/about", "https://other.com/x"],
        profile=_profile(),
    )
    assert r.self_cited is True
    assert r.self_match_reason and "cited_url" in r.self_match_reason


def test_self_cited_via_text_alias() -> None:
    r = evaluate(
        "ChatGPT が紹介する企業として、株式会社kiseeeen は注目です。",
        cited_urls=["https://other.com/x"],
        profile=_profile(),
    )
    assert r.self_cited is True
    assert r.self_match_reason and "alias" in r.self_match_reason


def test_self_cited_via_text_domain() -> None:
    r = evaluate(
        "詳しくは kiseeeen.co.jp を参照してください",
        cited_urls=["https://other.com/x"],
        profile=_profile(),
    )
    assert r.self_cited is True


def test_not_cited() -> None:
    r = evaluate(
        "全く関係ない回答",
        cited_urls=["https://example.com/foo"],
        profile=_profile(),
    )
    assert r.self_cited is False


def test_competitor_count_aggregation() -> None:
    r = evaluate(
        "テキスト",
        cited_urls=[
            "https://www.competitor1.com/a",
            "https://blog.competitor1.com/b",
            "https://competitor2.jp/x",
            "https://other.com/x",
        ],
        profile=_profile(),
    )
    counts = {c["domain"]: c["count"] for c in r.competitor_cited}
    assert counts == {"competitor1.com": 2, "competitor2.jp": 1}


def test_url_with_www_normalized() -> None:
    r = evaluate(
        "",
        cited_urls=["https://www.kiseeeen.co.jp/index"],
        profile=_profile(),
    )
    assert r.self_cited is True
