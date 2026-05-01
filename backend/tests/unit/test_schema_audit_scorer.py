from app.collectors.schema_audit.scorer import score_blocks


def test_empty_blocks_returns_zero() -> None:
    s = score_blocks([])
    assert s.score == 0
    assert s.missing_fields


def test_full_article_block_scores_100() -> None:
    blocks = [
        {
            "@type": "Article",
            "headline": "x",
            "author": {"@type": "Person", "name": "y"},
            "datePublished": "2026-05-01",
            "image": "https://x/y.jpg",
            "publisher": {"@type": "Organization", "name": "z"},
        }
    ]
    s = score_blocks(blocks)
    assert s.score == 100
    assert s.missing_fields == []


def test_partial_article_drops_score() -> None:
    blocks = [{"@type": "Article", "headline": "x"}]
    s = score_blocks(blocks)
    assert 0 < s.score < 100
    assert any("missing" in m and len(m["missing"]) >= 1 for m in s.missing_fields)


def test_faq_with_no_main_entity_zero() -> None:
    s = score_blocks([{"@type": "FAQPage"}])
    assert s.score == 0


def test_faq_with_main_entity_full() -> None:
    s = score_blocks([{"@type": "FAQPage", "mainEntity": [{"@type": "Question"}]}])
    assert s.score == 100
