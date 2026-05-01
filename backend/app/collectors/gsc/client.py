"""Google Search Console API クライアント。

Search Analytics API を呼んで「クエリ別日次メトリクス」「URL 別日次メトリクス」を取得する。

OAuth スコープ: https://www.googleapis.com/auth/webmasters.readonly
取得頻度: 週次(月曜 03:00 JST、W3-01 でスケジューラ設定)

GSC は API 呼び出しがレート制限される(1200 req/min)ため、retry_async で吸収。
"""

from dataclasses import dataclass
from datetime import date

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.collectors.google_oauth import GoogleOAuthCredentials
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


@dataclass(frozen=True, slots=True)
class GscRow:
    date: date
    query_text: str | None  # クエリ別の場合のみ
    page: str | None  # URL 別の場合のみ
    clicks: int
    impressions: int
    ctr: float
    position: float


class GscClient:
    def __init__(self, oauth: GoogleOAuthCredentials, site_url: str) -> None:
        if GSC_SCOPE not in oauth.scopes:
            raise ValueError(f"GSC scope ({GSC_SCOPE}) が含まれていません")
        self._creds = oauth.to_google_credentials()
        self._site_url = site_url  # 例: "sc-domain:kiseeeen.co.jp" or "https://kiseeeen.co.jp/"
        self._service = build("searchconsole", "v1", credentials=self._creds, cache_discovery=False)

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(HttpError, TimeoutError))
    async def query_metrics(
        self,
        start: date,
        end: date,
        *,
        dimensions: list[str],
        row_limit: int = 1000,
    ) -> list[GscRow]:
        """指定期間の集計を取得。dimensions は ['query'] or ['page'] or ['date', 'query'] 等。"""
        request_body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "dataState": "final",
        }
        # google-api-python-client は同期 API。FastAPI 内ではバックグラウンドジョブからのみ呼ぶ。
        resp = (
            self._service.searchanalytics()
            .query(siteUrl=self._site_url, body=request_body)
            .execute()
        )
        rows = resp.get("rows", [])
        log.info(
            "gsc_query_executed",
            site=self._site_url,
            start=start.isoformat(),
            end=end.isoformat(),
            dimensions=dimensions,
            row_count=len(rows),
        )
        return [_row_from_response(r, dimensions) for r in rows]


def _row_from_response(raw: dict, dimensions: list[str]) -> GscRow:
    keys = raw.get("keys", [])
    dim_map: dict[str, str] = dict(zip(dimensions, keys, strict=False))
    return GscRow(
        date=date.fromisoformat(dim_map.get("date", date.today().isoformat())),
        query_text=dim_map.get("query"),
        page=dim_map.get("page"),
        clicks=int(raw.get("clicks", 0)),
        impressions=int(raw.get("impressions", 0)),
        ctr=float(raw.get("ctr", 0.0)),
        position=float(raw.get("position", 0.0)),
    )
