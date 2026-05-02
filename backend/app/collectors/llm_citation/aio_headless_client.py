"""AI Overviews を自前 Headless Chromium で取得する引用モニタクライアント。

⚠️ 現状未使用(2026-05 時点、棚上げ)。
   実環境(VPS の ConoHa データセンタ IP)から www.google.com に Playwright で
   アクセスすると、即 google.com/sorry/index に飛ばされ Bot 検知でブロックされた。
   navigator.webdriver の偽装やリアルな user-agent / locale 設定だけでは突破不可能
   (TLS / canvas / WebGL fingerprint と IP の ASN 判定で総合的に検知される)。
   本ファイルは「将来の検討用」として残す。詳細は docs/implementation_plan.md
   13.5.4 を参照。

   現状の AIO 取得方針:
   - SerpApi キーがあれば SerpApi(aio_client.py)を使う
   - 無ければ AIO 列はスキップ
   - 中長期は DataForSEO への切替を推奨(月 $0.05〜10 で SerpApi の 1/100 以下)

実装方針(将来 IP 制約が外れた場合のため):
- Playwright + chromium、stealth 設定で navigator.webdriver を隠す
- 1 ジョブ実行ごとに browser を起動 → 全クエリ処理 → 終了(常駐させない)
- AI Overview 要素が無いクエリ(=AIO 出ない検索結果)は cited_urls=[] で返す
- CAPTCHA / consent 画面検知時は失敗にして次のクエリへ続行(無理に突破しない)
- レート制御: クエリ間に 5〜10 秒のランダム待機
"""

import asyncio
import contextlib
import random
import re
from urllib.parse import quote_plus

from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")


class AIOverviewsHeadlessClient:
    """ジョブ実行単位で 1 つの browser を共有するため、`runner` から
    `async with client.session():` で囲んで使う想定。

    SerpApi 版(`AIOverviewsCitationClient`)との違い:
    - 単発の `probe(query)` を連続で呼ぶスタイル
    - browser はセッション中ずっと開きっぱなし、close_session() で破棄
    """

    def __init__(self, *, hl: str = "ja", gl: str = "jp", headless: bool = True) -> None:
        self._hl = hl
        self._gl = gl
        self._headless = headless
        self._pw = None
        self._browser = None
        self._context = None

    async def __aenter__(self) -> "AIOverviewsHeadlessClient":
        await self.start_session()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close_session()

    async def start_session(self) -> None:
        self._pw = await async_playwright().start()
        # Bot 検知回避: AutomationControlled を無効化、リアルなユーザーエージェント
        self._browser = await self._pw.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        # navigator.webdriver を undefined に
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        log.info("aio_headless_session_started")

    async def close_session(self) -> None:
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        log.info("aio_headless_session_closed")

    async def probe(self, query_text: str) -> CitationProbeResult:
        if self._context is None:
            raise RuntimeError("call start_session() first or use async with")

        # クエリ毎にランダム待機(レート制御)
        await asyncio.sleep(random.uniform(5.0, 10.0))

        page = await self._context.new_page()
        try:
            url = (
                f"https://www.google.com/search?q={quote_plus(query_text)}"
                f"&hl={self._hl}&gl={self._gl}"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await _dismiss_consent_if_any(page)

            # AI Overview の有無を判定
            text, urls = await _extract_aio(page)
            log.info(
                "aio_headless_probe_done",
                query=query_text[:60],
                has_aio=bool(text),
                n_urls=len(urls),
            )
            return CitationProbeResult(
                llm_provider=LLMProviderEnum.aio,
                query_text=query_text,
                response_text=text,
                cited_urls=urls,
                raw_response={"source": "headless_chromium"},
            )
        finally:
            with contextlib.suppress(Exception):
                await page.close()


async def _dismiss_consent_if_any(page: Page) -> None:
    """Google の consent.google.com にリダイレクトされた場合は「同意」を押す。"""
    if "consent." in page.url:
        for label in ("同意する", "Accept all", "I agree"):
            try:
                await page.get_by_role("button", name=label).first.click(timeout=3_000)
                await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                return
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue


async def _extract_aio(page: Page) -> tuple[str, list[str]]:
    """検索結果ページから AI Overview のテキストと参照 URL を抽出する。

    Google は AIO セクションのクラス名を頻繁に変えるため、複数のセレクタ候補で試す。
    """
    text = ""
    urls: list[str] = []

    # AIO ブロックは現状 [data-attrid*="ai_overview"] や [aria-label*="AI Overview"] 等で識別される
    # 動的に変わるため複数候補を試行
    selectors = [
        '[data-async-context*="ai_overview"]',
        'div[aria-label*="AI Overview"]',
        'div[aria-label*="AI による概要"]',
        'div[jscontroller][data-rs]',  # 古い形式
    ]
    aio_block = None
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                aio_block = el
                break
        except Exception:
            continue

    if aio_block is None:
        return "", []

    try:
        text = (await aio_block.inner_text(timeout=5_000)).strip()
    except PlaywrightTimeoutError:
        text = ""

    # AIO 内部のリンクから URL を抽出
    try:
        anchors = aio_block.locator("a[href]")
        n = await anchors.count()
        for i in range(min(n, 20)):
            href = await anchors.nth(i).get_attribute("href")
            if not href:
                continue
            if href.startswith("/url?"):
                # /url?q=https://example.com&...
                from urllib.parse import parse_qs, urlparse

                qs = parse_qs(urlparse(href).query)
                actual = qs.get("q", [None])[0]
                if actual:
                    urls.append(actual)
            elif href.startswith("http"):
                urls.append(href)
    except Exception:
        pass

    if not urls and text:
        urls = URL_RE.findall(text)

    return text, list(dict.fromkeys(urls))
