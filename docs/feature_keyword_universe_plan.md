# 機能拡張計画書: データ駆動コンテンツ提案エンジン (Keyword Universe)

最終更新: 2026-05-06
ステータス: ドラフト(承認待ち)
関連: `docs/implementation_plan.md` Phase 2 戦略思考レイヤーの拡張

---

## 0. この計画書の位置づけ

現行の `query_suggestion` / `theme_suggestion` は `business_context` を入力に Gemini が「妥当そうなクエリ」を推測する設計で、**実需データ(GSC実績、サジェスト派生、競合見出し、LLM引用率)が反映されていない**。

本計画は以下の課題を解決する:

| 現状の課題 | 影響 |
|---|---|
| GSC `gsc_query_metrics` の実績がプロンプトに渡らない | 「DX 大阪は445imp/平均40位=惜しい」のような具体機会が見落とされる |
| Google/Bing のサジェスト派生語を取り込んでいない | サイトに表示されないが世の中で検索されている語(例: 業務効率化×AI周辺の20派生語)を発見できない |
| 競合の見出し/title を機械的に分析していない | 競合がカバーするキーワード群のリバースエンジニアリングができない |
| シノニムクラスタリングがない | 「DX」「IT化」「デジタル化」「業務効率化」を別物として扱い、戦略の重複・抜け漏れが発生 |
| 提案結果がクエリ単位で止まり、コンテンツブリーフ(タイトル/H2構成/対策語)まで降りない | 採用後の制作工程に手作業ギャップが残る |

ゴール: **オーナーが「対策キーワードを推奨して」と言わなくても、システムがGSC・サジェスト・競合・LLM引用率を統合してデータ駆動で提案する**状態にする。

---

## 1. 機能要件

### 1.1 ユースケース(オーナー視点)

| # | ユースケース | 期待する画面/操作 |
|---|---|---|
| UC-1 | 自社が抑えるべきキーワード候補を一覧で見たい | キーワードユニバース画面で50〜100語をクラスタ別に表示 |
| UC-2 | どのキーワードに機会があるかをデータで判断したい | imp実績/サジェスト派生数/競合カバー率/LLM引用率/優先度スコアを並列表示 |
| UC-3 | 採用キーワード群から記事/LPの構成案を生成したい | 候補をチェック→「ブリーフ生成」ボタン→title/h2/対策語が出る |
| UC-4 | ブリーフをそのまま WordPress 下書きまで進めたい | 既存 `wordpress_publisher` 経由で下書き化 |
| UC-5 | 提案根拠(なぜこのキーワードか)を確認したい | 各候補にホバー/詳細パネルで根拠データを開示 |

### 1.2 機能スコープ

#### 含む(MVP)
- F-1. Google サジェスト/Bing サジェストの自動収集ジョブ
- F-2. 競合上位ページの h1/h2/h3/title の自動収集ジョブ
- F-3. キーワードユニバース集計ロジック(GSC×サジェスト×競合×LLM引用率の統合)
- F-4. シノニムクラスタリング(辞書ベースの初期版)
- F-5. 優先度スコア計算
- F-6. キーワードユニバース閲覧UI
- F-7. コンテンツブリーフ生成(`content_brief` ユースケース)
- F-8. ブリーフ閲覧UI

#### 含まない(将来拡張)
- 競合のサイト全体クロール(Phase 1ではトップ+主要LPのみ)
- 検索ボリュームの絶対値取得(Google Ads API連携=別計画)
- 機械学習ベースのシノニムクラスタリング(辞書で十分動くため)
- ブリーフから本文ドラフトの自動生成(`content_draft` 既存ユースケース活用は別タスク)
- 多言語対応

---

## 2. アーキテクチャ

### 2.1 レイヤー構成

```
[Layer 1: 収集ジョブ] (新規)
  ├ collect_google_suggest      (週次)
  ├ collect_bing_suggest        (週次)
  └ collect_competitor_headings (月次)
        ↓ 書き込み
        keyword_suggestions (raw)

[Layer 2: 集計ジョブ] (新規)
  └ aggregate_keyword_universe  (週次)
        ↑ 読み込み
        keyword_suggestions / gsc_query_metrics / citation_logs / competitor_posts
        ↓ 書き込み
        keyword_universe (集計済)

[Layer 3: AI提案] (既存強化 + 新規)
  ├ query_suggestion v2 (既存強化: keyword_universe をプロンプト同梱)
  └ content_brief        (新規: 採用キーワード群から構成案生成)
        ↓ 書き込み
        content_briefs

[Layer 4: API/UI]
  ├ GET  /keyword-universe         一覧
  ├ POST /keyword-universe/refresh 再集計
  ├ POST /content-briefs/generate  ブリーフ生成
  └ GET  /content-briefs           一覧
```

### 2.2 既存テーブル/モジュールとの関係

- `gsc_query_metrics` … 自社流入実績(読み取り専用)
- `citation_logs` × `target_queries` … LLM引用率(読み取り専用)
- `competitors` × `competitor_posts` … 競合ドメイン(読み取り)。本計画で **competitor_headings(新規) または競合カラム追加** を検討
- `business_context`(tenants.business_context) … シードキーワード生成の入力
- `wordpress_publisher`(既存サービス) … ブリーフ → WP下書き連携先
- `theme_suggestion` … 廃止せず継続。`content_brief` は出力単位を「テーマ」より深い「ブリーフ」に拡張する位置づけ

---

## 3. データモデル

### 3.1 新規テーブル

#### 3.1.1 `keyword_suggestions`(収集生データ)

```sql
CREATE TABLE keyword_suggestions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source          TEXT NOT NULL,        -- 'google_suggest'|'bing_suggest'|'competitor_h2'|'competitor_h1'|'competitor_title'
  seed_keyword    TEXT,                 -- 元キーワード(competitor_*の場合はNULL可)
  derived_keyword TEXT NOT NULL,        -- サジェスト/見出しの実テキスト(小文字+全半角統一済み)
  raw_text        TEXT,                 -- 正規化前の原文
  metadata        JSONB NOT NULL DEFAULT '{}',  -- 競合URL/位置等
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_kws_tenant_fetched ON keyword_suggestions(tenant_id, fetched_at DESC);
CREATE INDEX ix_kws_tenant_source  ON keyword_suggestions(tenant_id, source);
CREATE UNIQUE INDEX uq_kws_tenant_source_seed_derived
  ON keyword_suggestions(tenant_id, source, COALESCE(seed_keyword,''), derived_keyword, fetched_at::date);
ALTER TABLE keyword_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_suggestions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON keyword_suggestions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

#### 3.1.2 `keyword_universe`(集計済キーワード辞書)

```sql
CREATE TABLE keyword_universe (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  keyword                     TEXT NOT NULL,           -- 正規化済み
  cluster_id                  TEXT NOT NULL,           -- 'dx'|'ai'|'efficiency'|'rpa'|'digitization'|'subsidy'|'local'|...
  intent                      TEXT,                    -- 'vendor_search'|'info'|'how'|'compare'|'tool'|'subsidy'
  is_geographic               BOOLEAN NOT NULL DEFAULT FALSE,

  -- メトリクス(集計時に上書き)
  gsc_imp_12m                 INTEGER NOT NULL DEFAULT 0,
  gsc_clicks_12m              INTEGER NOT NULL DEFAULT 0,
  gsc_avg_position            NUMERIC(6,2),
  suggest_derivative_count    INTEGER NOT NULL DEFAULT 0,
  competitor_coverage_count   INTEGER NOT NULL DEFAULT 0,
  llm_self_cite_rate          NUMERIC(5,4),            -- 0.0000-1.0000
  llm_competitor_cite_rate    NUMERIC(5,4),
  priority_score              NUMERIC(6,2) NOT NULL DEFAULT 0,
  opportunity_flag            TEXT,                    -- 'high_demand_no_coverage'|'near_top_3'|'low_demand'|null

  source_breakdown            JSONB NOT NULL DEFAULT '{}',  -- {gsc:bool, suggest:int, competitors:int, llm:int}
  last_aggregated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_ku_tenant_keyword ON keyword_universe(tenant_id, keyword);
CREATE INDEX ix_ku_tenant_cluster ON keyword_universe(tenant_id, cluster_id);
CREATE INDEX ix_ku_tenant_priority ON keyword_universe(tenant_id, priority_score DESC);
ALTER TABLE keyword_universe ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_universe FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON keyword_universe
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

#### 3.1.3 `content_briefs`(AI生成ブリーフ)

```sql
CREATE TABLE content_briefs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  primary_keyword     TEXT NOT NULL,
  cluster_id          TEXT NOT NULL,
  selected_keywords   TEXT[] NOT NULL,            -- 採用したキーワード群
  title               TEXT NOT NULL,
  meta_description    TEXT,
  h2_outline          JSONB NOT NULL,             -- [{h2, target_keywords[], rationale}]
  related_keywords    TEXT[] NOT NULL DEFAULT '{}',
  competitor_refs     JSONB NOT NULL DEFAULT '[]',-- 参考競合URL
  target_url_slug     TEXT,                       -- 推奨URLスラッグ
  rationale           TEXT,                       -- 選定根拠(LLM自由記述)
  status              TEXT NOT NULL DEFAULT 'draft', -- draft|adopted|published
  wp_draft_id         INTEGER,                    -- WP下書きID
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_cb_tenant_created ON content_briefs(tenant_id, created_at DESC);
CREATE INDEX ix_cb_tenant_status  ON content_briefs(tenant_id, status);
ALTER TABLE content_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_briefs FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON content_briefs
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

### 3.2 既存テーブル変更

なし(全て新規テーブルで対応)。`gsc_query_metrics` / `citation_logs` / `competitors` / `competitor_posts` は読み取り参照のみ。

### 3.3 シノニムクラスタ辞書

`backend/app/keyword_engine/clusters.yaml` を新設(コードと一緒にバージョン管理)。

```yaml
clusters:
  dx:
    label: "DX系"
    aliases: ["dx", "デジタルトランスフォーメーション", "dx化", "dx推進", "dx支援"]
  ai:
    label: "AI系"
    aliases: ["ai", "人工知能", "生成ai", "機械学習", "ai活用", "ai導入"]
  efficiency:
    label: "業務効率化系"
    aliases: ["業務効率化", "効率化", "業務改善", "業務改革", "生産性向上"]
  automation:
    label: "自動化/RPA系"
    aliases: ["自動化", "rpa", "オートメーション", "業務自動化"]
  digitization:
    label: "デジタル化系"
    aliases: ["デジタル化", "it化", "電子化", "ペーパーレス"]
  subsidy:
    label: "補助金系"
    aliases: ["補助金", "助成金", "it導入補助金", "事業再構築"]
  local_osaka:
    label: "大阪ローカル系"
    aliases: ["大阪", "大阪市", "大阪府", "関西", "近畿"]
    is_geographic: true
  local_hiranoku:
    label: "平野区ローカル系"
    aliases: ["平野区", "瓜破", "喜連瓜破", "東住吉区", "松原市", "八尾市"]
    is_geographic: true
  # … (10〜15クラスタ程度で開始)
```

### 3.4 優先度スコア(`priority_score`)算出式

```
priority_score = 
    log10(gsc_imp_12m + 1) * 30                         # 実需(自社既知)
  + log10(suggest_derivative_count + 1) * 20            # 派生豊富さ
  + competitor_coverage_count * 5                       # 競合がカバー = 重要シグナル
  + max(0, (51 - COALESCE(gsc_avg_position, 100))) * 0.5 # 上位に近いほど加点
  + (1 - COALESCE(llm_self_cite_rate, 0)) * 10          # 引用されていない = 機会
  - (is_geographic AND gsc_imp_12m < 5) * 15            # 地域系で実需0は減点
```

`opportunity_flag` の決定:

- `high_demand_no_coverage`: `suggest_derivative_count >= 5 AND gsc_imp_12m < 10`
- `near_top_3`: `gsc_avg_position BETWEEN 4 AND 15 AND gsc_imp_12m >= 50`
- `low_demand`: `suggest_derivative_count <= 1 AND gsc_imp_12m < 3 AND competitor_coverage_count == 0`
- それ以外は NULL

スコア式は YAML/設定ファイルで上書き可能にする(運用中のチューニング想定)。

---

## 4. 実装タスク分割(Phase 1〜5)

### Phase 1: サジェスト収集(0.5日)

#### 1-1. テーブル作成
- [ ] `alembic revision -m "add keyword_suggestions and keyword_universe tables"`
- [ ] `keyword_suggestions` / `keyword_universe` の DDL を upgrade に記述
- [ ] downgrade で逆操作
- [ ] `app/db/models/keyword_suggestion.py` / `keyword_universe.py` 追加

#### 1-2. サジェスト収集モジュール
- [ ] `app/keyword_engine/__init__.py` 新設
- [ ] `app/keyword_engine/suggest_collector.py`
  - `fetch_google_suggest(keyword: str) -> list[str]`
  - `fetch_bing_suggest(keyword: str) -> list[str]`
  - エンドポイント:
    - Google: `https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q=...`
    - Bing: `https://api.bing.com/osjson.aspx?query=...&mkt=ja-JP`
  - リトライ・タイムアウト: `httpx.AsyncClient(timeout=10)`、429時は exponential backoff(3回)
  - User-Agent: `Mozilla/5.0` 固定
- [ ] `app/keyword_engine/seed_builder.py`
  - `build_seeds(tenant) -> list[str]`: business_context から「中小企業 DX」「DX 大阪」等のシード20〜30本を生成
- [ ] `app/keyword_engine/normalizer.py`
  - `normalize(text: str) -> str`: 全半角統一、小文字化、両端空白除去

#### 1-3. ジョブ登録
- [ ] `app/scheduler/jobs/collect_keyword_suggestions.py`
- [ ] `app/scheduler/scheduler.py` に `CronTrigger(day_of_week='mon', hour=3)` で登録
- [ ] 失敗時 `JobExecutionLog` に記録(既存パターン踏襲)

#### 1-4. 受け入れ基準
- [ ] `python -m app.scheduler.jobs.collect_keyword_suggestions --tenant 7c59f23a-...` で 200+ 行が `keyword_suggestions` に入る
- [ ] 重複(同日同seed同derived)は UNIQUE 制約で弾かれる

---

### Phase 2: キーワードユニバース集計(1日)

#### 2-1. クラスタ辞書
- [ ] `backend/app/keyword_engine/clusters.yaml` 作成(10〜15クラスタ)
- [ ] `app/keyword_engine/cluster_matcher.py`
  - `classify(keyword: str) -> str`: keyword に最初に一致した cluster_id を返す
  - `is_geographic(cluster_id: str) -> bool`

#### 2-2. 集計ロジック
- [ ] `app/keyword_engine/aggregator.py`
  - `aggregate_universe(session, tenant_id) -> int`(処理件数を返す)
  - 入力ソース統合:
    1. `gsc_query_metrics`: 直近12ヶ月の query_text → imp/clicks/avg_position
    2. `keyword_suggestions`: source別の派生数を derived_keyword 単位で集約
    3. `competitor_posts`(または competitor_headings): 競合h2/title 出現数
    4. `citation_logs`: target_queries経由の self_cite_rate
  - 各 keyword をクラスタ判定 → priority_score 計算 → upsert
- [ ] スコア計算は `priority_calculator.py` に分離(設定ファイルから式を読む拡張余地)

#### 2-3. ジョブ登録
- [ ] `app/scheduler/jobs/aggregate_keyword_universe.py`
- [ ] CronTrigger: `day_of_week='mon', hour=4`(suggest 収集の1時間後)

#### 2-4. API + UI(最小)
- [ ] `app/api/v1/keyword_universe.py`
  - `GET /keyword-universe?cluster_id=&min_priority=&limit=`
  - `POST /keyword-universe/refresh`(手動再集計トリガ)
- [ ] `frontend/src/api/keyword_universe.ts`
- [ ] `frontend/src/pages/KeywordUniversePage.tsx`(クラスタ別タブ + ソート可能テーブル)
- [ ] サイドナビに「キーワード分析」追加

#### 2-5. 受け入れ基準
- [ ] `keyword_universe` に50〜200行が入る
- [ ] 「業務効率化 ai」が `opportunity_flag = high_demand_no_coverage` で出る
- [ ] 「大阪 DX 開発会社」が `opportunity_flag = near_top_3` 候補で出る
- [ ] UI でクラスタ別にソート/フィルタできる

---

### Phase 3: 競合見出し収集(0.5日)

#### 3-1. 取得対象の決定
- [ ] `competitors` テーブルにドメイン登録済みの競合に対して、トップページ + `/services/`, `/about/` 等の主要URLを対象
- [ ] 競合URL候補は `competitors.target_urls JSONB`(新カラム)で管理 / なければトップのみ

#### 3-2. 収集モジュール
- [ ] `app/keyword_engine/competitor_scraper.py`
  - `fetch_headings(url: str) -> dict`: title/h1/h2/h3 を BeautifulSoup で抽出
  - robots.txt 尊重(`urllib.robotparser`)、User-Agent 明記
- [ ] 結果を `keyword_suggestions` に source='competitor_h2' 等で保存

#### 3-3. ジョブ登録
- [ ] `app/scheduler/jobs/collect_competitor_headings.py`
- [ ] CronTrigger: 月初 1日 5時

#### 3-4. 受け入れ基準
- [ ] 登録競合3社のh2/h3が `keyword_suggestions` に入る
- [ ] 集計ジョブを再実行すると `competitor_coverage_count` が更新される

---

### Phase 4: query_suggestion v2(0.5日)

#### 4-1. プロンプト改修
- [ ] `prompts/query_suggestion.md` を改修。`keyword_universe` から優先度上位30件の{keyword, cluster, gsc_imp_12m, suggest_derivative_count, opportunity_flag}を埋め込む変数追加
- [ ] 新変数: `universe_top` / `clusters_summary`

#### 4-2. ユースケース改修
- [ ] `usecases/query_suggestion.py` で `keyword_universe` を読み込みプロンプトに渡す
- [ ] LLMには「ユニバースから既に高需要な語と機会の語を尊重しつつ補完候補を出す」と指示

#### 4-3. 受け入れ基準
- [ ] 提案された15〜20本のうち、80%以上が `keyword_universe` の上位50件と重複する
- [ ] reasoning 欄に「GSC実績/サジェスト派生/競合カバー」のいずれかへの言及がある

---

### Phase 5: content_brief 生成(1〜1.5日)

#### 5-1. 新規ユースケース
- [ ] `usecases/content_brief.py`
  - `generate_brief(session, tenant_id, primary_keyword, related_keyword_ids[]) -> dict`
  - 入力: 採用キーワード群(keyword_universe.id 配列)
  - 出力: title / meta / h2_outline / related_keywords / competitor_refs / target_url_slug / rationale
- [ ] プロンプト: `prompts/content_brief.md` 新規作成
  - 入力情報: 採用キーワード+各メトリクス、業種、author_profile、競合h2例
- [ ] 結果を `content_briefs` テーブルに保存

#### 5-2. API + UI
- [ ] `api/v1/content_briefs.py`
  - `POST /content-briefs/generate` `{primary_keyword, related_keyword_ids[]}`
  - `GET /content-briefs?status=`
  - `GET /content-briefs/{id}`
  - `POST /content-briefs/{id}/publish-wp`(既存 wordpress_publisher 呼び出し)
- [ ] フロント: KeywordUniversePage に「ブリーフ生成」ボタン
- [ ] `ContentBriefDetailPage.tsx`: ブリーフ詳細表示 + WP下書き化ボタン

#### 5-3. 受け入れ基準
- [ ] 「大阪 DX コンサル」を primary に `中小企業 DX 補助金` `DX 進まない 課題` を related で渡すと、title+h2 5本が JSON で返る
- [ ] 各 h2 に target_keywords が紐づく
- [ ] WP下書き化ボタンを押すと既存 `wordpress_publisher.create_draft()` が呼ばれて wp_draft_id が記録される

---

## 5. 受け入れ基準(全体)

### 5.1 機能受け入れ

シナリオテスト(オーナー目線):

1. **ジョブ実行**
   - `collect_keyword_suggestions` を手動実行 → 200+ 件が `keyword_suggestions` に入る
   - `aggregate_keyword_universe` を手動実行 → 50+ 行が `keyword_universe` に入り `priority_score > 0` が付く

2. **発見**
   - キーワード分析画面を開く
   - クラスタ「業務効率化系」を選ぶと「業務効率化 ai」が `opportunity_flag = high_demand_no_coverage` で表示される
   - クラスタ「DX系」で「大阪 DX 開発会社」が priority_score 上位に出る

3. **ブリーフ生成**
   - 「大阪 DX 開発会社」+ 関連3キーワードを選択 → 「ブリーフ生成」
   - title / meta / h2 5本+対策語 / 推奨URLスラッグが10秒以内に返る
   - 「WP下書き化」ボタンで既存 `kiseeeen.co.jp/wp-admin` に下書きが作成される

4. **再現性**
   - 翌週 `aggregate_keyword_universe` が自動実行され、`updated_at` が更新される
   - GSC で新規クエリが出現すると、次回集計時に keyword_universe に自動追加される

### 5.2 非機能受け入れ

- **パフォーマンス**: aggregate_keyword_universe が tenant 1件 30秒以内
- **エラー耐性**: Google/Bing サジェストAPIが429返却時、3回リトライ後はジョブ全体は完走する(その keyword だけスキップして JobExecutionLog に記録)
- **マルチテナント**: 全テーブル RLS で `app.tenant_id` フィルタ
- **追跡**: 各ジョブが JobExecutionLog に started/finished/error を記録
- **レート制限**: Googleサジェスト 1秒1req、Bing 1秒2req(連続呼び出し時)

---

## 6. リスクと緩和策

| リスク | 影響 | 緩和策 |
|---|---|---|
| Googleサジェスト非公式エンドポイントが将来停止 | 主要データソース消失 | (a)Bingで縮退運用、(b)将来 Google Ads API 連携計画を別途準備 |
| 競合スクレイピングで規約違反/負荷 | サイト側からブロック・苦情 | robots.txt 尊重、月1+5秒間隔、User-Agent 明記。動的レンダ要は対象外 |
| シノニム辞書の網羅不足 | クラスタリング精度低下 | YAML編集だけで運用追加可能、`unclassified` クラスタを設けて検出 |
| 優先度スコアが業種に偏る | 別業種テナント時に外れ値 | スコア式を `priority_calculator.py`+設定ファイルで差し替え可能に |
| LLM出力JSONの破損 | brief 生成失敗 | 既存 `_parse_json_array` パターン踏襲、リトライ1回 |
| keyword_universe 行数増加 | UIが重くなる | priority_score 上位500件で一覧をデフォルト制限、以降は検索ボックスで絞込 |

---

## 7. ロールアウトプラン

| 段階 | 内容 | 確認 |
|---|---|---|
| Step 1 | Phase 1 マージ → 1週間データ収集 | `keyword_suggestions` の蓄積確認 |
| Step 2 | Phase 2 マージ → ユニバース画面でデータ確認 | priority_score の分布が想定通りか |
| Step 3 | Phase 3 マージ → 競合カバー反映 | 既存の競合3社のh2が反映 |
| Step 4 | Phase 4 マージ → 既存 query_suggestion が改善 | A/B: v1とv2で生成結果を比較 |
| Step 5 | Phase 5 マージ → ブリーフ生成 + WP連携 | 1本のブリーフを WP下書きまで通す |

各 Phase は独立してリリース可能(Phase 1 がマージされなくても既存機能は動き続ける)。

---

## 8. 工数見積

| Phase | 想定工数 | 累計 |
|---|---|---|
| Phase 1: サジェスト収集 | 0.5日 | 0.5日 |
| Phase 2: ユニバース集計 + UI | 1.0日 | 1.5日 |
| Phase 3: 競合見出し収集 | 0.5日 | 2.0日 |
| Phase 4: query_suggestion v2 | 0.5日 | 2.5日 |
| Phase 5: content_brief + UI | 1.5日 | 4.0日 |

合計: **約4日**(Claude Codeのみで実装する前提)。

---

## 9. 着手順序の推奨

**Phase 1 → 2 → 4 → 5 → 3** の順を推奨:

- 1〜2 で「キーワードユニバース画面」が動き、データ駆動の判断が即始められる
- 4 で既存の `query_suggestion` が改善される(短い差分)
- 5 でブリーフ生成という最大の価値提供
- 3 はあると望ましいが必須ではない(Phase 5 の補強)

---

## 10. オープンクエスチョン(承認時に確定する項目)

1. **競合スクレイピング対象**: トップページのみ / 主要LP含む / 全サイトクロール → デフォルト「トップ+`competitors.target_urls` で指定」を推奨
2. **シノニムクラスタ初期セット**: 上記10クラスタで開始するか、追加するか
3. **優先度スコアの重み**: 上記式で運用開始 → 1ヶ月後にチューニングするか
4. **ブリーフから本文生成**: 既存 `content_draft` ユースケースとの連携を Phase 5 に含めるか別タスクか → **別タスク推奨**(Phase 5 はブリーフまで)
5. **多テナント運用**: 現在 active tenant が 1 のため、設計はマルチ前提だが Phase 1 では 1 テナントで動作確認

---

## 11. 承認後の最初のタスク

承認されたら以下から着手:

- [ ] T1: ブランチ作成 `feat/keyword-universe`
- [ ] T2: Alembic マイグレーション作成(Phase 1-1)
- [ ] T3: `clusters.yaml` を10クラスタで作成(承認後の修正前提)
- [ ] T4: `suggest_collector.py` PoC: `中小企業 DX` を1本叩いて結果を見る

T4 までで Phase 1 の50%が見える。
