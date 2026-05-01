"""引用判定: 回答テキストと引用 URL から、自社言及・競合言及を判定する。

仕様書 4.1.3:
- クライアントのドメイン名(例: kiseeeen.co.jp)
- クライアントのブランド名(例: kiseeeen, 株式会社kiseeeen)
- クライアントの代表者名(例: 黄瀬剛志)
- 引用 URL 一覧に自社ドメインが含まれるか

を文字列マッチで判定。コード判定にとどめ、AI には任せない。
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class MatchProfile:
    """テナントの自社マッチ条件 + 競合マッチ条件。"""

    self_domain: str
    self_aliases: list[str]  # ブランド名・代表者名・別名(空でも可)
    competitor_domains: list[str]


@dataclass(frozen=True, slots=True)
class MatchResult:
    self_cited: bool
    self_match_reason: str | None
    competitor_cited: list[dict]  # [{"domain": "...", "count": N}]


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _normalize(s: str) -> str:
    return s.strip().lower()


def evaluate(
    response_text: str,
    cited_urls: list[str],
    profile: MatchProfile,
) -> MatchResult:
    text_lc = response_text.lower() if response_text else ""
    self_domain_lc = _normalize(profile.self_domain)

    # 自社判定
    self_cited = False
    reason: str | None = None

    # 1. 引用 URL に自社ドメインを含むか
    for u in cited_urls:
        if self_domain_lc and self_domain_lc in _domain_of(u):
            self_cited = True
            reason = f"cited_url:{u}"
            break

    # 2. テキスト内にドメインが含まれるか
    if not self_cited and self_domain_lc and self_domain_lc in text_lc:
        self_cited = True
        reason = f"text_domain:{self_domain_lc}"

    # 3. テキスト内にエイリアス(ブランド名・代表者名)が含まれるか
    if not self_cited:
        for alias in profile.self_aliases:
            a = _normalize(alias)
            if a and a in text_lc:
                self_cited = True
                reason = f"text_alias:{alias}"
                break

    # 競合判定: 引用 URL のドメインで集計
    counts: dict[str, int] = {}
    for u in cited_urls:
        host = _domain_of(u)
        for cd in profile.competitor_domains:
            cd_lc = _normalize(cd)
            if cd_lc and cd_lc in host:
                counts[cd_lc] = counts.get(cd_lc, 0) + 1
                break

    competitor_cited = [{"domain": d, "count": c} for d, c in counts.items()]
    return MatchResult(
        self_cited=self_cited,
        self_match_reason=reason,
        competitor_cited=competitor_cited,
    )
