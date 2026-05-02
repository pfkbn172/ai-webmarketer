from app.services.kpi_aggregator import _branded_terms


def test_extracts_name_and_first_label_of_domain() -> None:
    assert _branded_terms("kiseeeen", "kiseeeen.co.jp") == ["kiseeeen"]


def test_dedups_common_terms() -> None:
    # tenant.name と domain 先頭ラベルが同じ場合は 1 つだけ
    assert _branded_terms("kiseeeen", "kiseeeen.co.jp") == ["kiseeeen"]


def test_includes_multi_word_name() -> None:
    out = _branded_terms("kiseeeen marketing", "example.com")
    assert "kiseeeen" in out
    assert "marketing" in out
    assert "example" in out


def test_skips_one_char_tokens() -> None:
    out = _branded_terms("k Inc", "x.com")
    # 1 文字は除外
    assert "k" not in out
    assert "inc" in out
    # x も 1 文字なので除外
    assert "x" not in out


def test_empty_inputs() -> None:
    assert _branded_terms("", "") == []
    assert _branded_terms("", "example.com") == ["example"]
