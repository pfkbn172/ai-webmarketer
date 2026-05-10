# 引き継ぎ: Marketer アプリへの新規 GA4 指標統合

**作成日**: 2026-05-10
**作成元**: kiseeeen.co.jp 本体側で SEO/AIO 計測強化を実装した直後の引き継ぎ
**対象アプリ**: `https://app.kiseeeen.co.jp/marketer`(VPS上)
**目的**: 本日 kiseeeen.co.jp 本体に追加した新規イベント/ディメンションを、Marketer アプリのダッシュボードでも閲覧できるようにする

---

## 1. 背景(必読)

`https://kiseeeen.co.jp` の **GA4 計測を 2026-05-10 に大幅拡張** しました。Marketer アプリは現状、GA4 / Search Console / PageSpeed Insights の標準指標を表示する作りになっているはずですが、**新たに 12 種類のカスタムイベントと 10 個のカスタムディメンションが GA4 側で計測されるようになった** ため、これらをアプリ側のダッシュボードでも表示できるよう改修してほしい、というのが今回の依頼です。

特に SEO/AIO(AI Optimization、AI 検索引用最適化)観点で価値の高い指標を追加しているので、それらを目立つように表示することがゴールです。

---

## 2. 対象 GA4 プロパティ情報

| 項目 | 値 |
|---|---|
| プロパティ名 | `pfkbn172_property_01` |
| プロパティ ID | `330427694` |
| データストリーム | `ウェブサイト`(ID: `4035282876`)/ `kiseeeen.co.jp/wp`(ID: `10478147980`) |
| メイン測定 ID | `G-5PVFQKHFJR` |
| キーイベント(コンバージョン) | `contact_complete`(`/contact/complete` 到達) |
| Measurement Protocol API Secret | アプリは GA4 Data API(読み取り)で取得するため不要。**書き込み用の Secret はサーバー側専用** |

Marketer アプリ側で GA4 Data API v1 を使ってデータ取得するときは、上記 **プロパティ ID `330427694`** を使います(measurement_id `G-5PVFQKHFJR` ではない点に注意)。

既存のアプリで GA4 接続が動いているはずなので、認証情報(サービスアカウント JSON もしくは OAuth トークン)はそのまま流用してください。

---

## 3. 追加された新規イベント一覧(12 種)

すべて **イベントスコープ**。下表の「パラメータ」列のキー名で送信されています。
`page_path` などはほぼ全イベント共通のため省略しました(必要に応じて取得してください)。

### A. AIO(AI 検索引用)直接効果測定

| # | イベント名 | 発火条件 | 主なパラメータ |
|---|---|---|---|
| A-1 | `ai_referral` | claude.ai / chatgpt.com / perplexity.ai / gemini.google.com / copilot.microsoft.com 等から流入したセッションの初回 PV | `ai_referrer_domain`, `page_referrer` |
| A-2 | `ai_crawler_visit` | サーバー側で User-Agent が AI ボットと判定された全 HTTP リクエスト(GPTBot / ClaudeBot / PerplexityBot / Google-Extended / OAI-SearchBot / Amazonbot / CCBot / Bytespider 等) | `crawler_name`, `crawler_ua`, `page_location` |
| A-3 | `llms_txt_fetch` | `/llms.txt` がフェッチされた回数(`/llms.php` ラッパー経由) | `crawler_name`, `crawler_ua` |

### B. コンテンツ品質シグナル

| # | イベント名 | 発火条件 | 主なパラメータ |
|---|---|---|---|
| B-4 | `article_read_complete` | スクロール 90% 以上 **かつ** エンゲージ時間 60 秒以上(短いページ・contact・animations 配下は除外) | `engaged_time_msec`, `max_scroll_pct`, `page_path` |
| B-5 | `internal_link_click` | 内部リンク `<a>` のクリック | `link_url`, `link_domain`, `link_text` |
| B-6 | `outbound_click` | 外部リンクのクリック | `link_url`, `link_domain`, `link_text`, `outbound_category`(`ai`/`social`/`booking`/`other`) |
| B-7 | `text_copy` | 本文からのコピー | `content_type`(`code`/`table`/`text`), `char_length` |

### C. ツール系ページ利用

| # | イベント名 | 発火条件 | 主なパラメータ |
|---|---|---|---|
| C-8 | `tool_use_complete` | `[data-tool-complete="<name>"]` 属性のついた要素のクリック | `tool_name` |

⚠️ **C-8 は WordPress(`/wp/`)側の各ツール記事に `data-tool-complete` 属性をまだ付けていない**ため、現状は発火していません。Marketer アプリ側で「この指標は WP 側の HTML に属性を仕込めば計測開始」とユーザーに案内できるよう、ヘルプテキストを添えると良いです。

### D. リード予兆(問い合わせフォーム関連)

| # | イベント名 | 発火条件 | 主なパラメータ |
|---|---|---|---|
| D-11 | `contact_confirm_view` | `/contact/confirm` 到達 | (page_path のみ) |
| D-12 | `cta_click` | LP の `.cta-btn` 等のクリック(`lp-common.js` が自動的に `data-cta` / `data-lp-id` を付与) | `cta_id`(`lp-header`/`lp-body`), `cta_location`, `lp_id`(LP ファイル名) |

### E. リテンション/権威性

| # | イベント名 | 発火条件 | 主なパラメータ |
|---|---|---|---|
| E-13 | `returning_visitor_engaged` | 2 回目以降の訪問 + エンゲージ 60 秒以上(localStorage で判定) | `visit_count` |
| E-14 | `content_share` / `url_copy` | navigator.share API 呼び出し / 現在 URL のコピー検知 | `share_method`(`navigator_share`/`url_copy`), `shared_url` |

---

## 4. 追加された新規カスタムディメンション(10 個)

すべて **イベントスコープ**。GA4 管理画面で登録済みなので、**24〜48 時間後から API で取得可能**になります(GA4 のディメンション伝播待ち)。

| ディメンション名(表示) | パラメータ名(API) | 紐づくイベント |
|---|---|---|
| AI Referrer Domain | `ai_referrer_domain` | ai_referral |
| AI Crawler Name | `crawler_name` | ai_crawler_visit, llms_txt_fetch |
| Content Type | `content_type` | text_copy |
| CTA ID | `cta_id` | cta_click |
| LP ID | `lp_id` | cta_click |
| Outbound Category | `outbound_category` | outbound_click |
| Link URL | `link_url` | internal_link_click, outbound_click |
| Tool Name | `tool_name` | tool_use_complete |
| Share Method | `share_method` | content_share, url_copy |
| Engaged Page Path | `page_path` | article_read_complete 等(汎用) |

API 経由でこれらを取得するときの **指定方法**:

- **イベントベース指標**: メトリクス `eventCount` + ディメンション `eventName` でフィルタする(例: `eventName == "ai_referral"`)
- **カスタムパラメータをディメンションとして使う場合**: ディメンション名は **`customEvent:<parameter_name>`** 形式
  - 例: `customEvent:ai_referrer_domain`、`customEvent:crawler_name`、`customEvent:tool_name`

---

## 5. Marketer アプリ側で実装する画面案

既存ダッシュボードのレイアウトに合わせて取捨選択してください。**優先度高(★★★)から低(★)** の順。

### ★★★ 新規セクション「AIO 効果」(目玉)

- **AI 流入(過去 30 日)**: ホストドメイン別棒グラフ
  - GA4 クエリ: `eventName == "ai_referral"` × `customEvent:ai_referrer_domain` × `eventCount`
- **AI クローラー訪問数(過去 30 日)**: クローラー名別折れ線+合計値カード
  - GA4 クエリ: `eventName == "ai_crawler_visit"` × `customEvent:crawler_name` × `eventCount`
- **AI クローラーがアクセスした人気ページ TOP10**:
  - `eventName == "ai_crawler_visit"` × `pagePath` × `eventCount`
- **llms.txt 取得回数**: シンプルなカウンター
  - `eventName == "llms_txt_fetch"` × `eventCount`

### ★★★ 新規セクション「コンタクトファネル」

ステップごとの離脱率を可視化:
1. `/contact/` 入力ページ PV(`page_path == "/contact/"`)
2. `contact_confirm_view` イベント発火数
3. `contact_complete` イベント発火数(キーイベント)

ファネルチャートで表示。**離脱が大きいステップが改善ポイント**。

### ★★★ 既存「コンバージョン」セクション拡張

現状おそらく `purchase` 系を見ているなら、**`contact_complete`** をメインのキーイベントとして表示するよう変更してください。`purchase` は GA4 デフォルトで残置されていますが発火しません(EC サイトではない)。

### ★★ 新規セクション「コンテンツ品質」

- **完読率**: ページ別 `article_read_complete` イベント数 ÷ ページ別 PV
  - GA4 クエリ: 同一 `pagePath` で `eventCount` を 2 回(`article_read_complete` と `page_view`)取って割る
- **コピーされたコンテンツ TOP10**: `text_copy` × `pagePath` + `customEvent:content_type` で `code`/`table`/`text` 別
- **外部参照したリンク**: `outbound_click` × `customEvent:outbound_category` でカテゴリ別に集計

### ★★ 新規セクション「LP 別パフォーマンス」

- **LP 別 CTA クリック数**: `eventName == "cta_click"` × `customEvent:lp_id`
- **LP 別 CTA → コンバージョン率**: ファネル分析 API もしくは事前計算
  - 分子: `lp_id` 別 `cta_click` 数
  - 分母: 同 `lp_id` の LP セッション数
- **CTA 位置別**: `customEvent:cta_id`(`lp-header` vs `lp-body`)で比較すると LP デザインの示唆になる

### ★ 新規セクション「ツール利用」(WP 側で属性付与後に有効化)

- **ツール完走数**: `tool_use_complete` × `customEvent:tool_name`
- まだ属性が無い場合は「未実装」の旨をアプリ上に表示

### ★ サブ指標(既存セクションへの追加で十分)

- 再訪エンゲージ数: `returning_visitor_engaged` イベント数
- シェア・URL コピー数: `content_share` + `url_copy` の合算
- 内部リンク CTR: `internal_link_click` ÷ PV(関連記事ナビ品質の指標)

---

## 6. データ反映の注意

| 種類 | 反映タイミング |
|---|---|
| イベント発火 | リアルタイム(数秒〜数分) |
| GA4 標準レポート画面 | 24〜48 時間後 |
| **カスタムディメンション(API 取得)** | **登録から 24〜48 時間後** |
| Search Console データ | 1〜2 日遅れ(既存実装で対応済のはず) |

→ Marketer アプリで「データなし」と表示される場合、**24 時間以上経過しているか必ず確認** してください。新ディメンション登録は 2026-05-10 です。

---

## 7. 確認用テストイベント

開発中の動作確認には以下が便利:

- **GA4 → DebugView**(`https://analytics.google.com/analytics/web/?pli=1#/p330427694/realtime/debug-view`)
  - 自分の PC からサイト訪問+操作 → リアルタイムでイベント確認
- **GA4 → リアルタイム → イベント数**
  - 集約値で確認(数秒の遅延)

特定イベントを意図的に発火させたい場合:
- `ai_referral` → ブラウザのコンソールで `document.referrer` を細工した状態で kiseeeen.co.jp を開く(難しいので発火を待つ)
- `cta_click` → 任意の LP で `.cta-btn` をクリック
- `article_read_complete` → 長い記事をスクロール最下部まで進めて 60 秒以上滞在
- `text_copy` → 任意の本文を選択してコピー
- `ai_crawler_visit` → サーバー側のみ、`curl -A 'GPTBot/1.0' https://kiseeeen.co.jp/` で疑似発火可能

---

## 8. 既存実装との共存

- Marketer アプリが GA4 Data API のキャッシュ機構を持っている場合、新ディメンションが伝播する前にキャッシュされた「該当データなし」レスポンスが固定化されないよう、**初回伝播後にキャッシュをクリア**する手順を組んでください。
- 既存の Search Console / PSI セクションには影響なし。サイトに JS を追加していますが PageSpeed への影響は軽微(analytics.js は async + defer 相当の遅延読み込み構造)。

---

## 9. プライバシー/コンプライアンス

- `ai_crawler_visit` / `llms_txt_fetch` は `crawler_ua` を 200 文字に切り詰めて送信(個人情報含まず)
- `text_copy` の中身(コピーされた文字列そのもの)は **送信していない**(文字数のみ)
- `content_share` の `shared_url` は当該ページの URL のみ
- 既存のプライバシーポリシー(`/privacy-policy`)で GA4 利用が記載されていれば追加対応不要

---

## 10. 参考: 主要ファイル(本体側、参照のみ・編集不要)

すべて `https://kiseeeen.co.jp` のリポジトリ(VPS 上の本体コード)にあります。

| パス | 役割 |
|---|---|
| `/js/analytics.js` | クライアントサイドイベント全種(A-1 / B-4〜7 / C-8 / D-11,12 / E-13,14)の発火元 |
| `/includes/server-analytics.php` | サーバーサイド: AI クローラー検知 + Measurement Protocol 送信 |
| `/llms.php` + `.htaccess` の `RewriteRule ^llms\.txt$ /llms.php` | A-3 計測 |
| `/lp/_shared/lp-common.js` の `tagCTAs()` | LP の CTA 自動タグ付け |
| `/config.php` + `.env` | `GA4_MEASUREMENT_ID`, `GA4_API_SECRET` 環境変数 |

Marketer アプリでこれらを直接読み込む必要は **ありません**。GA4 Data API でディメンション/メトリクスを問い合わせるだけで完結します。

---

## 作業の進め方の推奨

1. まず **★★★ AIO 効果セクション** の 4 ウィジェット(AI 流入 / AI クローラー数 / クローラーアクセスページ / llms.txt 取得数)を実装 — これが今回の目玉
2. 次に **★★★ コンタクトファネル** — 既存コンバージョン画面を拡張する形で
3. **★★ コンテンツ品質 / LP 別パフォーマンス**
4. **★ ツール利用 / サブ指標**

ディメンションの API 反映には 24〜48 時間かかるので、本日の作業中は **空のレスポンスが返る前提でモック値で UI 構築 → 反映後に実データに切り替え** が効率的です。

実装中に追加で本体側の修正が必要だと判明したら(イベントパラメータの追加など)、本ドキュメントを更新してから本体側も追従させてください。

---

**この引き継ぎ文書はここまでです。本ドキュメントだけで作業を完結できる構成にしています。不明点があればドキュメント本文の該当セクションを参照してから、それでも判断できない場合のみユーザー(Tsuyoshi Kise)に確認してください。**
