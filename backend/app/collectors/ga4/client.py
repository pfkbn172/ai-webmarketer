"""Google Analytics Data API(GA4)クライアント。

仕様書 4.1.2: セッション・ユーザー・直帰率・コンバージョン・流入元・ページ別パフォーマンス。
Phase 1 では「日次のサイト全体メトリクス + organic セッション」を取得する最小実装。
"""

from dataclasses import dataclass
from datetime import date

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    FilterExpression,
    FilterExpressionList,
    Metric,
    RunReportRequest,
)
from google.analytics.data_v1beta.types import Filter as GaFilter

from app.collectors.google_oauth import GoogleOAuthCredentials
from app.utils.logger import get_logger

log = get_logger(__name__)

GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


@dataclass(frozen=True, slots=True)
class Ga4DailyRow:
    date: date
    sessions: int
    users: int
    bounce_rate: float | None
    conversions: int
    organic_sessions: int


@dataclass(frozen=True, slots=True)
class Ga4AiReferralRow:
    date: date
    source_host: str
    sessions: int


@dataclass(frozen=True, slots=True)
class Ga4PageRow:
    date: date
    page_path: str
    sessions: int
    users: int
    conversions: int


@dataclass(frozen=True, slots=True)
class Ga4HourlyRow:
    date: date
    hour: int  # 0〜23
    sessions: int


@dataclass(frozen=True, slots=True)
class Ga4ReferralRow:
    date: date
    source: str
    medium: str
    sessions: int


@dataclass(frozen=True, slots=True)
class Ga4ReferralHourlyRow:
    date: date
    hour: int
    source: str
    medium: str
    sessions: int


# --- カスタムイベント(2026-05 追加分)用の dataclass --------------------------


@dataclass(frozen=True, slots=True)
class Ga4AiReferralEventRow:
    date: date
    ai_referrer_domain: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4AiCrawlerRow:
    date: date
    crawler_name: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4AiCrawlerPageRow:
    date: date
    crawler_name: str
    page_path: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4LlmsTxtFetchRow:
    date: date
    crawler_name: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4ArticleReadCompleteRow:
    date: date
    page_path: str
    event_count: int
    page_views: int


@dataclass(frozen=True, slots=True)
class Ga4TextCopyRow:
    date: date
    page_path: str
    content_type: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4OutboundClickRow:
    date: date
    outbound_category: str
    link_domain: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4CtaClickRow:
    date: date
    lp_id: str
    cta_id: str
    event_count: int
    lp_sessions: int


@dataclass(frozen=True, slots=True)
class Ga4ToolUseRow:
    date: date
    tool_name: str
    event_count: int


@dataclass(frozen=True, slots=True)
class Ga4EngagementSignalRow:
    date: date
    event_name: str
    sub_key: str
    event_count: int


# 統合エンゲージメント集計対象のイベント名(`engagement_signals` で or_group 化)。
ENGAGEMENT_SIGNAL_EVENTS: tuple[str, ...] = (
    "returning_visitor_engaged",
    "content_share",
    "url_copy",
    "internal_link_click",
    "contact_confirm_view",
)


def _normalize_path(raw: str | None) -> str:
    """page_path 表記揺れを抑える(クエリ・フラグメント除去、末尾 / の正規化)。"""
    if not raw:
        return "/"
    s = raw.split("#", 1)[0].split("?", 1)[0]
    if not s:
        return "/"
    if s != "/" and s.endswith("/"):
        s = s.rstrip("/")
    return s[:1024]


# AI チャットからの流入を判定する参照元ホスト名(GA4 sessionSource)。
# GA4 が source として返す値は、参照元 URL のホスト名(www.* は除いた形)。
# 値の整形は collector 側で行う。
AI_REFERRAL_HOSTS: tuple[str, ...] = (
    "chatgpt.com",
    "chat.openai.com",
    "claude.ai",
    "perplexity.ai",
    "www.perplexity.ai",
    "gemini.google.com",
    "bard.google.com",
    "copilot.microsoft.com",
    "www.bing.com",  # Bing Chat / Copilot 経由は bing 経由になることがある
)


class Ga4Client:
    def __init__(self, oauth: GoogleOAuthCredentials, property_id: str) -> None:
        if GA4_SCOPE not in oauth.scopes:
            raise ValueError(f"GA4 scope ({GA4_SCOPE}) が含まれていません")
        self._client = BetaAnalyticsDataClient(credentials=oauth.to_google_credentials())
        # property_id 形式: "properties/123456789"
        self._property = property_id if property_id.startswith("properties/") else f"properties/{property_id}"

    async def daily_metrics(self, start: date, end: date) -> list[Ga4DailyRow]:
        rows = self._fetch_daily_total(start, end)
        organic_map = self._fetch_daily_organic(start, end)
        return [
            Ga4DailyRow(
                date=r["date"],
                sessions=r["sessions"],
                users=r["users"],
                bounce_rate=r["bounce_rate"],
                conversions=r["conversions"],
                organic_sessions=organic_map.get(r["date"], 0),
            )
            for r in rows
        ]

    def _fetch_daily_total(self, start: date, end: date) -> list[dict]:
        # GA4 の "conversions" メトリクスは property のキーイベント合計を返す。
        # 本プロパティではキーイベントは contact_complete のみのため、
        # conversions == contact_complete 件数として扱える(2026-05 移行時点)。
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="bounceRate"),
                Metric(name="conversions"),
            ],
        )
        resp = self._client.run_report(req)
        return [
            {
                "date": _parse_ga4_date(row.dimension_values[0].value),
                "sessions": int(row.metric_values[0].value or 0),
                "users": int(row.metric_values[1].value or 0),
                "bounce_rate": float(row.metric_values[2].value) if row.metric_values[2].value else None,
                "conversions": int(float(row.metric_values[3].value or 0)),
            }
            for row in resp.rows
        ]

    async def ai_referrals(self, start: date, end: date) -> list[Ga4AiReferralRow]:
        """AI チャット経由の参照元ホスト × 日次セッション。

        sessionSource ディメンションを取得し、AI_REFERRAL_HOSTS にマッチした行のみ返す。
        GA4 側の値は通常ホスト名形式("chatgpt.com" 等)で返るため、ホワイトリスト判定で十分。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date"), Dimension(name="sessionSource")],
            metrics=[Metric(name="sessions")],
            dimension_filter=FilterExpression(
                or_group=FilterExpressionList(
                    expressions=[
                        FilterExpression(
                            filter=GaFilter(
                                field_name="sessionSource",
                                string_filter=GaFilter.StringFilter(
                                    value=host, match_type=GaFilter.StringFilter.MatchType.EXACT
                                ),
                            ),
                        )
                        for host in AI_REFERRAL_HOSTS
                    ]
                )
            ),
        )
        resp = self._client.run_report(req)
        out: list[Ga4AiReferralRow] = []
        for row in resp.rows:
            sessions = int(row.metric_values[0].value or 0)
            if sessions <= 0:
                continue
            out.append(
                Ga4AiReferralRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    source_host=row.dimension_values[1].value,
                    sessions=sessions,
                )
            )
        return out

    async def page_metrics(self, start: date, end: date, *, top_n: int = 200) -> list[Ga4PageRow]:
        """日次 × pagePath のセッション・ユーザー・コンバージョン。

        Top N URL に絞ることで、API の row_limit と DB 容量を節約。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date"), Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="conversions"),
            ],
            limit=top_n,
        )
        resp = self._client.run_report(req)
        out: list[Ga4PageRow] = []
        for row in resp.rows:
            sessions = int(row.metric_values[0].value or 0)
            if sessions <= 0:
                continue
            out.append(
                Ga4PageRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    page_path=row.dimension_values[1].value,
                    sessions=sessions,
                    users=int(row.metric_values[1].value or 0),
                    conversions=int(float(row.metric_values[2].value or 0)),
                )
            )
        return out

    async def hourly_metrics(self, start: date, end: date) -> list[Ga4HourlyRow]:
        """日付 × 時間帯のセッション数。GA4 の dateHour ディメンション(YYYYMMDDHH)を使う。

        曜日 × 時間帯ヒートマップで「どの時間帯にトラフィックが集中しているか」を
        可視化するため。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="dateHour")],
            metrics=[Metric(name="sessions")],
        )
        resp = self._client.run_report(req)
        out: list[Ga4HourlyRow] = []
        for row in resp.rows:
            sessions = int(row.metric_values[0].value or 0)
            if sessions <= 0:
                continue
            raw = row.dimension_values[0].value or ""
            if len(raw) != 10 or not raw.isdigit():
                continue
            d = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            h = int(raw[8:10])
            if not 0 <= h <= 23:
                continue
            out.append(Ga4HourlyRow(date=d, hour=h, sessions=sessions))
        return out

    async def referrals_daily(self, start: date, end: date) -> list[Ga4ReferralRow]:
        """全リファラ × 日次セッション。

        Direct は GA4 上 source='(direct)' / medium='(none)' で返る。
        organic は medium='organic'、SNS や外部サイトは medium='referral'。
        広告は cpc / paid 等。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium"),
            ],
            metrics=[Metric(name="sessions")],
        )
        resp = self._client.run_report(req)
        out: list[Ga4ReferralRow] = []
        for row in resp.rows:
            sessions = int(row.metric_values[0].value or 0)
            if sessions <= 0:
                continue
            out.append(
                Ga4ReferralRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    source=(row.dimension_values[1].value or "")[:255] or "(not set)",
                    medium=(row.dimension_values[2].value or "")[:64] or "(not set)",
                    sessions=sessions,
                )
            )
        return out

    async def referrals_hourly(
        self, start: date, end: date
    ) -> list[Ga4ReferralHourlyRow]:
        """全リファラ × 時間帯 × 日次セッション。

        dateHour(YYYYMMDDHH)+ source + medium を使う。cardinality が大きくなるため、
        本メソッドは「最近 N 日」など短期窓で叩く想定。バックフィル時は呼び出し側で
        週単位など短いチャンクに分割する。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="dateHour"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium"),
            ],
            metrics=[Metric(name="sessions")],
        )
        resp = self._client.run_report(req)
        out: list[Ga4ReferralHourlyRow] = []
        for row in resp.rows:
            sessions = int(row.metric_values[0].value or 0)
            if sessions <= 0:
                continue
            raw = row.dimension_values[0].value or ""
            if len(raw) != 10 or not raw.isdigit():
                continue
            d = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            h = int(raw[8:10])
            if not 0 <= h <= 23:
                continue
            out.append(
                Ga4ReferralHourlyRow(
                    date=d,
                    hour=h,
                    source=(row.dimension_values[1].value or "")[:255] or "(not set)",
                    medium=(row.dimension_values[2].value or "")[:64] or "(not set)",
                    sessions=sessions,
                )
            )
        return out

    # --- カスタムイベント(2026-05 追加分)取得メソッド ----------------------

    def _event_filter(self, event_name: str) -> FilterExpression:
        return FilterExpression(
            filter=GaFilter(
                field_name="eventName",
                string_filter=GaFilter.StringFilter(
                    value=event_name,
                    match_type=GaFilter.StringFilter.MatchType.EXACT,
                ),
            ),
        )

    async def ai_referral_events(
        self, start: date, end: date
    ) -> list[Ga4AiReferralEventRow]:
        """ai_referral イベント × ai_referrer_domain の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:ai_referrer_domain"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("ai_referral"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4AiReferralEventRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4AiReferralEventRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    ai_referrer_domain=(row.dimension_values[1].value or "(not set)")[:255],
                    event_count=cnt,
                )
            )
        return out

    async def ai_crawler_visits(self, start: date, end: date) -> list[Ga4AiCrawlerRow]:
        """ai_crawler_visit イベント × crawler_name の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:crawler_name"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("ai_crawler_visit"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4AiCrawlerRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4AiCrawlerRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    crawler_name=(row.dimension_values[1].value or "(not set)")[:128],
                    event_count=cnt,
                )
            )
        return out

    async def ai_crawler_pages(
        self, start: date, end: date, *, top_n: int = 1000
    ) -> list[Ga4AiCrawlerPageRow]:
        """ai_crawler_visit イベント × crawler_name × pagePath の日次集計。

        カーディナリティ抑制のため `top_n` で絞る。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:crawler_name"),
                Dimension(name="pagePath"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("ai_crawler_visit"),
            limit=top_n,
        )
        resp = self._client.run_report(req)
        out: list[Ga4AiCrawlerPageRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4AiCrawlerPageRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    crawler_name=(row.dimension_values[1].value or "(not set)")[:128],
                    page_path=_normalize_path(row.dimension_values[2].value),
                    event_count=cnt,
                )
            )
        return out

    async def llms_txt_fetches(
        self, start: date, end: date
    ) -> list[Ga4LlmsTxtFetchRow]:
        """llms_txt_fetch イベント × crawler_name の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:crawler_name"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("llms_txt_fetch"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4LlmsTxtFetchRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4LlmsTxtFetchRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    crawler_name=(row.dimension_values[1].value or "(not set)")[:128],
                    event_count=cnt,
                )
            )
        return out

    async def article_read_completes(
        self, start: date, end: date
    ) -> list[Ga4ArticleReadCompleteRow]:
        """article_read_complete イベント × pagePath の日次集計。

        完読率算出のため、同条件の page_view eventCount(`page_views`)も同梱して返す。
        """
        # 1) 完読イベント
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date"), Dimension(name="pagePath")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("article_read_complete"),
        )
        resp = self._client.run_report(req)
        completes: dict[tuple[date, str], int] = {}
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            d = _parse_ga4_date(row.dimension_values[0].value)
            p = _normalize_path(row.dimension_values[1].value)
            completes[(d, p)] = cnt

        if not completes:
            return []

        # 2) 同パス × 同日の page_view を取りに行く
        pv_req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date"), Dimension(name="pagePath")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("page_view"),
        )
        pv_resp = self._client.run_report(pv_req)
        page_views: dict[tuple[date, str], int] = {}
        for row in pv_resp.rows:
            d = _parse_ga4_date(row.dimension_values[0].value)
            p = _normalize_path(row.dimension_values[1].value)
            page_views[(d, p)] = int(float(row.metric_values[0].value or 0))

        return [
            Ga4ArticleReadCompleteRow(
                date=d,
                page_path=p,
                event_count=cnt,
                page_views=page_views.get((d, p), 0),
            )
            for (d, p), cnt in completes.items()
        ]

    async def text_copy_events(
        self, start: date, end: date
    ) -> list[Ga4TextCopyRow]:
        """text_copy イベント × pagePath × content_type の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="pagePath"),
                Dimension(name="customEvent:content_type"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("text_copy"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4TextCopyRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4TextCopyRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    page_path=_normalize_path(row.dimension_values[1].value),
                    content_type=(row.dimension_values[2].value or "(not set)")[:32],
                    event_count=cnt,
                )
            )
        return out

    async def outbound_click_events(
        self, start: date, end: date
    ) -> list[Ga4OutboundClickRow]:
        """outbound_click イベント × outbound_category × linkDomain の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:outbound_category"),
                Dimension(name="linkDomain"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("outbound_click"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4OutboundClickRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4OutboundClickRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    outbound_category=(row.dimension_values[1].value or "(not set)")[:32],
                    link_domain=(row.dimension_values[2].value or "(not set)")[:255],
                    event_count=cnt,
                )
            )
        return out

    async def cta_click_events(
        self, start: date, end: date
    ) -> list[Ga4CtaClickRow]:
        """cta_click イベント × lp_id × cta_id の日次集計 + LP セッション同梱。"""
        # 1) CTA クリック数
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:lp_id"),
                Dimension(name="customEvent:cta_id"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("cta_click"),
        )
        resp = self._client.run_report(req)
        clicks: list[tuple[date, str, str, int]] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            d = _parse_ga4_date(row.dimension_values[0].value)
            lp = (row.dimension_values[1].value or "(not set)")[:128]
            cta = (row.dimension_values[2].value or "(not set)")[:64]
            clicks.append((d, lp, cta, cnt))

        if not clicks:
            return []

        # 2) LP セッション(分母): pagePath が /lp/ 配下のもの × lp_id 別
        sess_req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:lp_id"),
            ],
            metrics=[Metric(name="sessions")],
            dimension_filter=FilterExpression(
                filter=GaFilter(
                    field_name="pagePath",
                    string_filter=GaFilter.StringFilter(
                        value="/lp/",
                        match_type=GaFilter.StringFilter.MatchType.CONTAINS,
                    ),
                ),
            ),
        )
        sess_resp = self._client.run_report(sess_req)
        lp_sessions: dict[tuple[date, str], int] = {}
        for row in sess_resp.rows:
            d = _parse_ga4_date(row.dimension_values[0].value)
            lp = (row.dimension_values[1].value or "(not set)")[:128]
            lp_sessions[(d, lp)] = int(row.metric_values[0].value or 0)

        return [
            Ga4CtaClickRow(
                date=d,
                lp_id=lp,
                cta_id=cta,
                event_count=cnt,
                lp_sessions=lp_sessions.get((d, lp), 0),
            )
            for (d, lp, cta, cnt) in clicks
        ]

    async def tool_use_events(
        self, start: date, end: date
    ) -> list[Ga4ToolUseRow]:
        """tool_use_complete イベント × tool_name の日次集計。"""
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="customEvent:tool_name"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=self._event_filter("tool_use_complete"),
        )
        resp = self._client.run_report(req)
        out: list[Ga4ToolUseRow] = []
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            out.append(
                Ga4ToolUseRow(
                    date=_parse_ga4_date(row.dimension_values[0].value),
                    tool_name=(row.dimension_values[1].value or "(not set)")[:128],
                    event_count=cnt,
                )
            )
        return out

    async def engagement_signals(
        self, start: date, end: date
    ) -> list[Ga4EngagementSignalRow]:
        """エンゲージメント系 5 イベントの統合日次集計。

        対象: returning_visitor_engaged / content_share / url_copy /
              internal_link_click / contact_confirm_view
        sub_key は share_method を採る(他イベントでは "-")。
        """
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="eventName"),
                Dimension(name="customEvent:share_method"),
            ],
            metrics=[Metric(name="eventCount")],
            dimension_filter=FilterExpression(
                or_group=FilterExpressionList(
                    expressions=[
                        FilterExpression(
                            filter=GaFilter(
                                field_name="eventName",
                                string_filter=GaFilter.StringFilter(
                                    value=ev,
                                    match_type=GaFilter.StringFilter.MatchType.EXACT,
                                ),
                            ),
                        )
                        for ev in ENGAGEMENT_SIGNAL_EVENTS
                    ]
                )
            ),
        )
        resp = self._client.run_report(req)
        # 同じ (date, event_name) で sub_key 違いの複数行が出るので、
        # share_method があるイベント以外は sub_key="-" に集約する。
        bucket: dict[tuple[date, str, str], int] = {}
        for row in resp.rows:
            cnt = int(float(row.metric_values[0].value or 0))
            if cnt <= 0:
                continue
            d = _parse_ga4_date(row.dimension_values[0].value)
            ev = (row.dimension_values[1].value or "")[:64]
            sm = (row.dimension_values[2].value or "").strip()
            if ev in ("content_share", "url_copy") and sm:
                sub_key = sm[:255]
            else:
                sub_key = "-"
            bucket[(d, ev, sub_key)] = bucket.get((d, ev, sub_key), 0) + cnt

        return [
            Ga4EngagementSignalRow(
                date=d, event_name=ev, sub_key=sub_key, event_count=cnt
            )
            for (d, ev, sub_key), cnt in bucket.items()
        ]

    def _fetch_daily_organic(self, start: date, end: date) -> dict[date, int]:
        req = RunReportRequest(
            property=self._property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="date"), Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            dimension_filter=FilterExpression(
                filter=GaFilter(
                    field_name="sessionDefaultChannelGroup",
                    string_filter=GaFilter.StringFilter(value="Organic Search"),
                ),
            ),
        )
        resp = self._client.run_report(req)
        return {
            _parse_ga4_date(row.dimension_values[0].value): int(row.metric_values[0].value or 0)
            for row in resp.rows
        }


def _parse_ga4_date(s: str) -> date:
    """GA4 の date dimension は 'YYYYMMDD' 形式の文字列。"""
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
