"""Gemini を Web grounding 付きで呼ぶ引用モニタクライアント。

仕様書 6.3: AI 処理用 Gemini と引用モニタ用 Gemini は別 API キーで分離可能。
本ファイルは抽象レイヤを通さず、ハードコードで grounding を使う。

URL 解決の課題:
    Gemini API の Grounding 機能は引用元 URL を
        https://vertexaisearch.cloud.google.com/grounding-api-redirect/<token>
    のラッパー形式で返す。`web.uri` も `web.title` から推測した URL も同じく
    ラッパーのため、ドメイン照合では self_cited 判定が常に false になる問題があった。

    対策:
    1) chunk.web.domain(SDK が出してくれる場合あり)を最優先で採用
    2) 無ければラッパー URL を HEAD/GET でリダイレクト追跡して実 URL を取得
       同一クエリ内ではキャッシュして HEAD 重複呼出しを抑える
"""

import re

import httpx
from google import genai
from google.genai import types as gtypes

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")
WRAPPER_HOST = "vertexaisearch.cloud.google.com"


class GeminiCitationClient:
    """引用モニタ用 Gemini クライアント。

    モデルのデフォルトは gemini-2.5-flash-lite。理由:
    - Gemini Free Tier の RPD(1 日あたりリクエスト数)が 2.5 Flash だと 20 件しかなく、
      週次 20 クエリのモニタで即枠切れになる
    - 2.5 Flash-Lite は同 Free Tier で RPD ~1000(2026-05 時点)あり、引用モニタの
      用途(クエリ → Web 検索 → 回答 + 引用 URL を取得)には品質十分
    - AI 処理用(月次レポート / コンテンツドラフト等)は品質要件が高いため、
      ai_engine/providers/gemini_adapter.py の方は 2.5 Flash のまま維持する

    課金プラン(Tier 1+)に切り替えた場合は model 引数で 2.5 Flash や 2.5 Pro を
    渡せば即切替可能。
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(Exception,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        config = gtypes.GenerateContentConfig(
            tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=query_text, config=config
        )
        text = resp.text or ""
        raw_uris: list[str] = []
        # SDK が直接ドメインを出してくれる場合の補助情報を集める
        domain_hints: list[str] = []
        for cand in (resp.candidates or []):
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for chunk in (getattr(gm, "grounding_chunks", []) or []):
                web = getattr(chunk, "web", None)
                if not web:
                    continue
                u = getattr(web, "uri", None)
                if u:
                    raw_uris.append(u)
                d = getattr(web, "domain", None)
                if d:
                    domain_hints.append(d)
        # text 中の URL も集める(grounding 外で言及された場合のため)
        if not raw_uris:
            raw_uris = URL_RE.findall(text)

        urls = await _resolve_wrapper_urls(raw_uris, domain_hints)
        log.info(
            "gemini_probe_done",
            query=query_text[:60],
            n_urls=len(urls),
            wrapper_resolved=sum(1 for u in raw_uris if WRAPPER_HOST in u),
        )
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.gemini,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )


async def _resolve_wrapper_urls(
    raw_uris: list[str], domain_hints: list[str]
) -> list[str]:
    """vertexaisearch のラッパー URL を実 URL に展開する。

    - ラッパー以外の URL はそのまま採用
    - ラッパー URL は HEAD で Location を取得(同一 URL は 1 回だけ)
    - HEAD が失敗(403 等)した場合は domain_hints 由来の合成 URL "https://<domain>/" にフォールバック
    """
    cache: dict[str, str | None] = {}
    out: list[str] = []
    timeout = httpx.Timeout(10.0)

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        for i, u in enumerate(raw_uris):
            if WRAPPER_HOST not in u:
                out.append(u)
                continue
            if u in cache:
                resolved = cache[u]
                if resolved:
                    out.append(resolved)
                continue
            resolved: str | None = None
            try:
                # HEAD ではブロックされる場合があるので GET も試す
                for method in ("HEAD", "GET"):
                    r = await client.request(method, u)
                    loc = r.headers.get("location")
                    if loc:
                        resolved = loc
                        break
                    if 200 <= r.status_code < 300:
                        # リダイレクトせず本文を返してきた場合は実 URL を取れない
                        resolved = None
                        break
            except httpx.HTTPError as exc:
                log.warning("gemini_wrapper_resolve_failed", url=u[:80], error=str(exc))
            cache[u] = resolved
            if resolved:
                out.append(resolved)
            elif i < len(domain_hints) and domain_hints[i]:
                # 順序対応のフォールバック(grounding chunks は順序保持)
                out.append(f"https://{domain_hints[i]}/")

    return list(dict.fromkeys(out))  # 重複除去
