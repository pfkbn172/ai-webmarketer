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
