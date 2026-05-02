# AIウェブマーケターSaaS 実装計画

株式会社kiseeeen 内部ドキュメント|Version 1.0|2026年5月

本書は仕様書 `ai_webmarketer_requirements_v2.1.md`(以下「仕様書」)セクション 19 への回答であり、Phase 1(自社運用 MVP・4 週間)の着手前に固める設計と計画をまとめたものである。

設計指針 `ai_webmarketer_design_guidelines.md`(以下「指針」)を実装中の常時参照ドキュメントとし、本書はその上位の合意事項を扱う。

---

## 0. 仕様書からの不明点・追加質問(キセ承認済み回答付き)

実装着手前のレビューで次の 10 点を確認済み。回答は確定事項として以降のセクションに反映する。

| # | 論点 | 仕様書の該当 | 確定回答 |
|---|---|---|---|
| Q1 | 認証方式 | 4.5.1 / 9.2 | Phase 1 から最初からアプリ認証(メール+パスワード)。BASIC 認証は経由しない |
| Q2 | ターゲットクエリ規模 | 4.1.3 / 4.2.1 | Phase 1 上限は **20 本/テナント**(クエリ数 × 5LLM × 週次 = 約 100 リクエスト/週) |
| Q3 | AI 起点判定 | 4.4.2, 5.1 `ai_origin` | UTM パラメータ(`utm_source=chatgpt` など)+ AI 推定の併用、フォーム未通過時は AI 推定で fallback |
| Q4 | 異常検知閾値 | 4.4.3 | システムデフォルト + テナントごとに上書き可能 |
| Q5 | 引用モニタの実行方針 | 4.1.3 | 毎週同じプロンプトでターゲットクエリを全件実行(週次再現性確保) |
| Q6 | 月次レポート生成タイミング | 7.1 | **毎月 3 日 7:00 JST** に変更(GSC/GA4 の前月分データ確定遅延を吸収) |
| Q7 | バックアップ | 8.3 | Phase 1 ではローカル pg_dump(`/var/backups/marketer/`)+ 別ディスクパス保管。B2 連携は既存設定の有無を確認後に判断、Phase 2 で本格化 |
| Q8 | CSV エクスポート | 4.5.10 | Phase 1 は同期ダウンロードで開始、レコード数が一定閾値を超えるとバックグラウンド処理に切り替える設計余地を残す |
| Q9 | 著者プロフィール | 4.2.2 | テナントあたり **複数著者対応**(法律事務所など複数士業を抱える業態を想定)。`author_profiles` を `tenants` に対し 1:N に変更 |
| Q10 | テナント分離の長期方針 | 5.2 | RLS 維持で十分。Phase 3 でも DB スキーマ分離は採用しない |

### 残存する確認事項(Phase 1 進行中に解消)

- **Q11**: 既存 VPS に rclone + Backblaze B2 の認証設定が稼働中かどうか(`/root/.config/rclone/rclone.conf` 等の存在)。Phase 1 Week 1 中に確認、なければローカル世代管理のみで開始。
- **Q12**: PM2 を `pm2-root` か `pm2-react-dev` のどちらに乗せるか。**推奨は `pm2-root`**(既存の Node/Python アプリ群と同じ流儀)。

---

## 1. 技術スタック(B 案 = PM2 + apt PostgreSQL 確定版)

仕様書 14 章の指針内で、設計合意セッションでの判断を反映。

### 1.1 採用スタック

| 領域 | 採用 | 主な却下理由を持つ代替案 |
|---|---|---|
| バックエンド言語 | **Python 3.12**(システム標準) | Node.js: LLM SDK のエコシステムは Python が最厚 |
| Web フレームワーク | **FastAPI** + Uvicorn | Flask: 非同期/型ヒントの一級対応が弱い / Django: ORM 縛りで RLS 自由度が落ちる |
| ORM | **SQLAlchemy 2.x (async)** | Tortoise ORM: エコシステム規模 / 生 SQL: マイグレーション管理が手間 |
| マイグレーション | **Alembic** | yoyo, dbmate: Alembic は SQLAlchemy と一体運用しやすい |
| バリデーション | **Pydantic v2** | dataclass 自前: AI 構造化出力と統一できない |
| DB | **PostgreSQL 16**(apt インストール、`pgcrypto` / `pg_trgm` 拡張) | MySQL: RLS 不在 |
| HTTP クライアント | **httpx (async)** | requests: 同期のみ |
| ジョブ実行 | **APScheduler**(`marketer-worker` 常駐)+ GHA schedule で外形監視 | Celery + Redis: Phase 1 では Redis 増設が過剰 / cron: VPS 死亡で一緒に止まる |
| プロセス管理 | **PM2(`pm2-root` 配下)** | systemd unit: 既存運用との一貫性で PM2 |
| 認証 | **自前 JWT + Argon2id + httpOnly Cookie** | Auth0 / Supabase Auth: 商材化での外部依存・コスト懸念 |
| 暗号化 | **Fernet**(`cryptography` ライブラリ) | AES-GCM 自前: Fernet が安全な既製品 |
| AI SDK | `google-genai`(Gemini)/ `anthropic` / `openai` / `httpx` 直叩き(Perplexity / SerpApi) | LangChain: Provider 切替を自前で持つ方針と矛盾 |
| ログ | **structlog**(JSON 構造化、tenant_id を contextvar で自動付与) | logging 標準: 構造化が手間 |
| テスト | **pytest + pytest-asyncio + httpx.AsyncClient + Playwright(主要動線 E2E)** | unittest: 過渡期 |
| Lint / 型 | **ruff + mypy**(strict 漸進) | flake8 + black: ruff で統一 |
| フロント | **React 18 + TypeScript + Vite** | Next.js: SSR 不要、サブパス構成が複雑化 |
| ルーティング | **React Router v6**(`basename="/marketer/"`) | TanStack Router: サブパス事例が薄い |
| 状態管理 | **TanStack Query + Zustand** | Redux Toolkit: 過剰 |
| UI | **Tailwind CSS + shadcn/ui** | MUI / Chakra: 編集的・落ち着いた色調を Tailwind+shadcn で構築 |
| グラフ | **Recharts** | ECharts: オーバースペック |
| CI | **GitHub Actions**(lint + test、scheduled-watchdog) | Jenkins / CircleCI: 既存フローとの整合 |
| デプロイ | **GitHub → VPS 上 `git pull` → migrate → `pm2 reload`** | Docker Compose: B 案で不採用(別途議論で確定) |
| Web サーバ | 既存 Nginx に `marketer.conf` を `include` | 別建て Caddy: 運用分裂 |

### 1.2 主要 Python ライブラリ(`backend/requirements.txt` の主成分)

```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
alembic>=1.13
pydantic>=2.7
pydantic-settings>=2.3
python-jose[cryptography]>=3.3
argon2-cffi>=23.1
cryptography>=42
httpx>=0.27
structlog>=24
apscheduler>=3.10
jinja2>=3.1
google-genai>=0.5
anthropic>=0.34
openai>=1.40
beautifulsoup4>=4.12      # 構造化データ抽出用
lxml>=5
feedparser>=6.0           # 競合 RSS
google-auth>=2.30         # GSC / GA4 OAuth
google-api-python-client>=2.130
google-analytics-data>=0.18
resend>=2.0
```

### 1.3 主要 Node ライブラリ(`frontend/package.json` の主成分)

```
react / react-dom / react-router-dom
typescript / vite
@tanstack/react-query / zustand
tailwindcss / @radix-ui/* (shadcn)
recharts
zod / react-hook-form
date-fns
```

---

## 2. データモデル詳細(テーブル定義)

設計指針 4.1 / 4.2 に沿って、Repository パターン + RLS の二重防御を前提に設計。すべての主キーは UUID v7(時系列順序性を保ちつつ衝突しにくい)。

### 2.1 Enum 型

```sql
CREATE TYPE user_role AS ENUM ('admin', 'client');
CREATE TYPE compliance_type AS ENUM ('general', 'lawyer', 'medical', 'realestate', 'finance');
CREATE TYPE content_status AS ENUM ('draft', 'ai_generating', 'review', 'published', 'archived');
CREATE TYPE inquiry_source AS ENUM ('web', 'email', 'phone', 'ai', 'other');
CREATE TYPE ai_origin AS ENUM ('chatgpt', 'claude', 'perplexity', 'gemini', 'aio');
CREATE TYPE inquiry_status AS ENUM ('new', 'in_progress', 'contracted', 'lost');
CREATE TYPE llm_provider AS ENUM ('chatgpt', 'claude', 'perplexity', 'gemini', 'aio');
CREATE TYPE ai_use_case AS ENUM (
  'monthly_report', 'weekly_summary', 'theme_suggestion', 'content_draft',
  'compliance_check', 'inquiry_structuring', 'eeat_analysis', 'citation_opportunity'
);
CREATE TYPE ai_provider AS ENUM ('gemini', 'claude', 'openai', 'perplexity');
CREATE TYPE credential_provider AS ENUM (
  'gsc', 'ga4', 'wordpress', 'resend',
  'serpapi', 'gemini_ai_engine', 'gemini_citation_monitor',
  'openai', 'anthropic', 'perplexity', 'facebook'
);
CREATE TYPE job_status AS ENUM ('queued', 'running', 'success', 'failed', 'skipped');
```

### 2.2 主要テーブル DDL(抜粋)

完全な DDL は Alembic マイグレーションで管理する。ここでは設計判断が伴う箇所のみ示す。

```sql
-- 全テーブル共通: tenant_id を持つ場合は最初のカラム、複合 INDEX の先頭に置く

CREATE TABLE tenants (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  industry        TEXT,
  domain          TEXT NOT NULL,
  compliance_type compliance_type NOT NULL DEFAULT 'general',
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,            -- Argon2id
  role          user_role NOT NULL DEFAULT 'client',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);

CREATE TABLE user_tenants (
  user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, tenant_id)
);

CREATE TABLE tenant_credentials (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  provider        credential_provider NOT NULL,
  encrypted_data  BYTEA NOT NULL,             -- Fernet 暗号化、JSON を平文で持つ前段で暗号化
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, provider)
);

CREATE TABLE target_queries (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  query_text           TEXT NOT NULL,
  cluster_id           TEXT,                  -- Pillar/Cluster 構造を表現
  priority             SMALLINT NOT NULL DEFAULT 3,
  expected_conversion  SMALLINT NOT NULL DEFAULT 3,
  search_intent        TEXT,
  is_active            BOOLEAN NOT NULL DEFAULT TRUE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, query_text)
);
CREATE INDEX ix_target_queries_tenant_active ON target_queries(tenant_id, is_active);

CREATE TABLE competitors (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  domain      TEXT NOT NULL,
  brand_name  TEXT,
  rss_url     TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ix_competitors_tenant ON competitors(tenant_id);

CREATE TABLE author_profiles (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name                  TEXT NOT NULL,
  job_title             TEXT,
  works_for             TEXT,
  alumni_of             JSONB DEFAULT '[]'::jsonb,
  credentials           JSONB DEFAULT '[]'::jsonb,
  expertise             JSONB DEFAULT '[]'::jsonb,
  publications          JSONB DEFAULT '[]'::jsonb,
  speaking_engagements  JSONB DEFAULT '[]'::jsonb,
  awards                JSONB DEFAULT '[]'::jsonb,
  bio_short             TEXT,
  bio_long              TEXT,
  social_profiles       JSONB DEFAULT '[]'::jsonb,
  is_primary            BOOLEAN NOT NULL DEFAULT FALSE,  -- Q9: 1:N 対応、主著者を 1 名指定
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_author_profiles_tenant ON author_profiles(tenant_id);
CREATE UNIQUE INDEX uq_author_profiles_primary
  ON author_profiles(tenant_id) WHERE is_primary;

CREATE TABLE contents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  url           TEXT,
  title         TEXT NOT NULL,
  status        content_status NOT NULL DEFAULT 'draft',
  pillar_id     TEXT,
  cluster_id    TEXT,
  schema_score  SMALLINT,                    -- 0..100
  draft_md      TEXT,                        -- AI 生成 Markdown ドラフト
  published_at  TIMESTAMPTZ,
  wp_post_id    BIGINT,
  primary_author_id UUID REFERENCES author_profiles(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, url)
);
CREATE INDEX ix_contents_tenant_status ON contents(tenant_id, status, published_at DESC);

CREATE TABLE content_metrics (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id  UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
  tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- 非正規化(RLS のため)
  date        DATE NOT NULL,
  sessions    INT NOT NULL DEFAULT 0,
  citations   INT NOT NULL DEFAULT 0,
  UNIQUE (content_id, date)
);
CREATE INDEX ix_content_metrics_tenant_date ON content_metrics(tenant_id, date DESC);

CREATE TABLE citation_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  query_id        UUID NOT NULL REFERENCES target_queries(id) ON DELETE CASCADE,
  llm_provider    llm_provider NOT NULL,
  query_date      DATE NOT NULL,
  response_text   TEXT,
  cited_urls      JSONB DEFAULT '[]'::jsonb,
  self_cited      BOOLEAN NOT NULL DEFAULT FALSE,
  competitor_cited JSONB DEFAULT '[]'::jsonb,  -- [{domain, count}]
  raw_response    JSONB,                       -- デバッグ用
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_citation_logs_tenant_query_date
  ON citation_logs(tenant_id, query_id, query_date DESC);

CREATE TABLE inquiries (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  received_at    TIMESTAMPTZ NOT NULL,
  industry       TEXT,
  company_size   TEXT,
  content_text   TEXT,
  source_channel inquiry_source NOT NULL,
  ai_origin      ai_origin,                    -- nullable
  status         inquiry_status NOT NULL DEFAULT 'new',
  raw_payload    JSONB,                        -- Webhook 受信時の元データ
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_inquiries_tenant_received ON inquiries(tenant_id, received_at DESC);

CREATE TABLE reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period          CHAR(7) NOT NULL,            -- 'YYYY-MM'
  report_type     TEXT NOT NULL,               -- 'monthly' | 'weekly'
  summary_html    TEXT,
  action_plan     JSONB,
  generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, period, report_type)
);

CREATE TABLE kpi_logs (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  date               DATE NOT NULL,
  sessions           INT,
  clicks             INT,
  impressions        INT,
  avg_position       NUMERIC(5,2),
  ai_citation_count  INT,
  named_search_count INT,
  inquiries_count    INT,
  UNIQUE (tenant_id, date)
);
CREATE INDEX ix_kpi_logs_tenant_date ON kpi_logs(tenant_id, date DESC);

CREATE TABLE ai_provider_configs (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  use_case           ai_use_case NOT NULL,
  provider           ai_provider NOT NULL,
  model_name         TEXT NOT NULL,
  prompt_template_id UUID REFERENCES prompt_templates(id),
  temperature        NUMERIC(3,2) DEFAULT 0.7,
  max_tokens         INT DEFAULT 2000,
  fallback_provider  ai_provider,                 -- 失敗時フォールバック先
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, use_case)
);

CREATE TABLE prompt_templates (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  use_case      ai_use_case NOT NULL,
  version       INT NOT NULL DEFAULT 1,
  file_path     TEXT NOT NULL,                  -- ai_engine/prompts/<file>.md を参照
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (use_case, version)
);

CREATE TABLE job_execution_logs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,  -- システムジョブは NULL
  job_name     TEXT NOT NULL,
  status       job_status NOT NULL,
  attempt_no   SMALLINT NOT NULL DEFAULT 1,
  started_at   TIMESTAMPTZ NOT NULL,
  finished_at  TIMESTAMPTZ,
  error_text   TEXT,
  metadata     JSONB
);
CREATE INDEX ix_job_logs_name_started ON job_execution_logs(job_name, started_at DESC);

CREATE TABLE audit_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID REFERENCES tenants(id) ON DELETE SET NULL,
  user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
  action        TEXT NOT NULL,
  target_table  TEXT,
  target_id     UUID,
  payload       JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_tenant_created ON audit_logs(tenant_id, created_at DESC);

-- 構造化データ監査ログ
CREATE TABLE schema_audit_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  content_id      UUID REFERENCES contents(id) ON DELETE CASCADE,
  url             TEXT NOT NULL,
  audit_date      DATE NOT NULL,
  score           SMALLINT NOT NULL,
  missing_fields  JSONB DEFAULT '[]'::jsonb,
  raw_jsonld      JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_schema_audit_tenant_date ON schema_audit_logs(tenant_id, audit_date DESC);
```

### 2.3 RLS ポリシー(全テナントテーブルに一律適用)

```sql
-- 例: target_queries
ALTER TABLE target_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE target_queries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON target_queries
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

リクエストごとに `SET LOCAL app.tenant_id = '<uuid>'` を発行。`current_setting('app.tenant_id', true)` の第二引数 `true` で、未設定時は NULL を返してすべて拒否される設計。

`admin` ロールユーザーのリクエストに対しては、必要時に `app.tenant_id` を切替できるよう、専用 DB ロール(例: `marketer_admin`)に `BYPASSRLS` 属性を付ける選択肢もあるが、**Phase 1 では BYPASSRLS は使用せず、admin もリクエスト時にどのテナントを操作するか明示する**(管理画面で「現在のテナント」を選択させる UI 設計)。

### 2.4 暗号化対象

| テーブル/カラム | 方式 | 用途 |
|---|---|---|
| `tenant_credentials.encrypted_data` | Fernet | API キー、OAuth refresh token、Application Password 等。JSON 化してから暗号化 |
| `users.password_hash` | Argon2id | ログインパスワード |

Fernet の鍵は環境変数 `MARKETER_FERNET_KEY` で供給。鍵ローテーション手順は Phase 2 で別途文書化。

### 2.5 インデックス戦略

- すべてのテナント所属テーブルで `(tenant_id, ...)` の複合 INDEX を先頭に
- 時系列カラム(`*_date`, `*_at`)は DESC INDEX で履歴取得を高速化
- JSONB の cited_urls / competitor_cited 等は GIN INDEX を Phase 2 で必要に応じて追加(Phase 1 は不要)

### 2.6 ER 関係(主要)

```
tenants 1─N users(user_tenants 経由 N:N)
tenants 1─N target_queries 1─N citation_logs
tenants 1─N competitors
tenants 1─N author_profiles 1─N contents (primary_author_id)
tenants 1─N contents 1─N content_metrics
tenants 1─N inquiries
tenants 1─N reports
tenants 1─N kpi_logs
tenants 1─N ai_provider_configs N─1 prompt_templates
tenants 1─N tenant_credentials
tenants 1─N schema_audit_logs N─1 contents (nullable)
tenants 0─N job_execution_logs
tenants 0─N audit_logs N─1 users
```

---

## 3. ディレクトリ構成・モジュール責務

指針 1.3 / 3.1 に沿って機能ごとの垂直分割。各ファイルは推奨 300 行・厳守 500 行以内。

```
/var/www/ai-web-marketer/
├─ docs/                                ← 全ドキュメント集約
│   ├─ ai_webmarketer_requirements_v2.1.md
│   ├─ ai_webmarketer_design_guidelines.md
│   ├─ ai_webmarketer_claude_code_handoff.md
│   ├─ vps_environment.md
│   └─ implementation_plan.md           ← 本書
├─ backend/
│   ├─ pyproject.toml
│   ├─ requirements.txt
│   ├─ alembic.ini
│   ├─ alembic/
│   │   ├─ env.py
│   │   └─ versions/
│   ├─ app/
│   │   ├─ main.py                      ← FastAPI app 生成、ルータ集約(<100 行)
│   │   ├─ settings.py                  ← Pydantic Settings(環境変数読込)
│   │   ├─ api/
│   │   │   ├─ deps.py                  ← 依存性注入(現在ユーザー、テナント解決)
│   │   │   └─ v1/
│   │   │       ├─ auth.py
│   │   │       ├─ tenants.py
│   │   │       ├─ target_queries.py
│   │   │       ├─ citation_logs.py
│   │   │       ├─ contents.py
│   │   │       ├─ inquiries.py
│   │   │       ├─ reports.py
│   │   │       ├─ exports.py
│   │   │       ├─ author_profiles.py
│   │   │       ├─ competitors.py
│   │   │       ├─ kpi.py
│   │   │       └─ settings_api.py      ← AI Provider 設定、認証情報、通知設定
│   │   ├─ webhook/
│   │   │   ├─ wordpress.py
│   │   │   └─ inquiry.py
│   │   ├─ collectors/
│   │   │   ├─ gsc/
│   │   │   │   ├─ client.py
│   │   │   │   └─ runner.py
│   │   │   ├─ ga4/
│   │   │   │   ├─ client.py
│   │   │   │   └─ runner.py
│   │   │   ├─ llm_citation/
│   │   │   │   ├─ runner.py            ← 全 LLM を順次実行、結果統合
│   │   │   │   ├─ chatgpt_client.py
│   │   │   │   ├─ claude_client.py
│   │   │   │   ├─ perplexity_client.py
│   │   │   │   ├─ gemini_client.py
│   │   │   │   ├─ aio_client.py        ← SerpApi 経由
│   │   │   │   └─ matcher.py           ← 文字列マッチ判定
│   │   │   ├─ schema_audit/
│   │   │   │   ├─ fetcher.py
│   │   │   │   ├─ parser.py
│   │   │   │   └─ scorer.py
│   │   │   └─ competitor_rss/
│   │   │       └─ client.py
│   │   ├─ ai_engine/
│   │   │   ├─ providers/
│   │   │   │   ├─ base.py              ← AIProvider ABC
│   │   │   │   ├─ schemas.py           ← ProviderResponse, TokenUsage
│   │   │   │   ├─ gemini_adapter.py    ← Phase 1 実装
│   │   │   │   ├─ claude_adapter.py    ← Phase 2(スケルトンのみ)
│   │   │   │   ├─ openai_adapter.py    ← Phase 2(スケルトンのみ)
│   │   │   │   ├─ perplexity_adapter.py ← Phase 2(スケルトンのみ)
│   │   │   │   ├─ mock_adapter.py      ← テスト用
│   │   │   │   └─ factory.py           ← AIProviderFactory
│   │   │   ├─ usecases/
│   │   │   │   ├─ monthly_report.py
│   │   │   │   ├─ weekly_summary.py
│   │   │   │   ├─ theme_suggestion.py
│   │   │   │   ├─ content_draft.py
│   │   │   │   ├─ compliance_check.py
│   │   │   │   ├─ inquiry_structuring.py
│   │   │   │   ├─ eeat_analysis.py
│   │   │   │   └─ citation_opportunity.py
│   │   │   ├─ prompts/                 ← .md + Jinja2 プレースホルダ
│   │   │   │   ├─ monthly_report.md
│   │   │   │   ├─ weekly_summary.md
│   │   │   │   ├─ theme_suggestion.md
│   │   │   │   ├─ content_draft.md
│   │   │   │   ├─ compliance_check.md
│   │   │   │   ├─ inquiry_structuring.md
│   │   │   │   ├─ eeat_analysis.md
│   │   │   │   └─ citation_opportunity.md
│   │   │   ├─ schemas/                 ← Pydantic 入出力モデル
│   │   │   └─ template_loader.py
│   │   ├─ db/
│   │   │   ├─ base.py                  ← async engine, sessionmaker, RLS 設定
│   │   │   ├─ models/
│   │   │   │   ├─ tenant.py
│   │   │   │   ├─ user.py
│   │   │   │   ├─ target_query.py
│   │   │   │   ├─ citation_log.py
│   │   │   │   ├─ content.py
│   │   │   │   ├─ inquiry.py
│   │   │   │   ├─ report.py
│   │   │   │   ├─ kpi_log.py
│   │   │   │   ├─ author_profile.py
│   │   │   │   ├─ competitor.py
│   │   │   │   ├─ ai_provider_config.py
│   │   │   │   ├─ prompt_template.py
│   │   │   │   ├─ tenant_credential.py
│   │   │   │   ├─ job_execution_log.py
│   │   │   │   └─ audit_log.py
│   │   │   └─ repositories/
│   │   │       ├─ base.py              ← BaseRepository(tenant_id 必須化)
│   │   │       └─ <model>.py           ← 各モデルに対応
│   │   ├─ auth/
│   │   │   ├─ middleware.py            ← FastAPI middleware(JWT 検証 + tenant_context 設定)
│   │   │   ├─ tenant_context.py        ← contextvars.ContextVar
│   │   │   ├─ password.py              ← Argon2id ラッパー
│   │   │   ├─ jwt.py                   ← JWT 発行/検証
│   │   │   └─ deps.py                  ← FastAPI Depends 提供
│   │   ├─ scheduler/
│   │   │   ├─ scheduler.py             ← APScheduler セットアップ
│   │   │   └─ jobs/
│   │   │       ├─ collect_gsc.py
│   │   │       ├─ collect_ga4.py
│   │   │       ├─ monitor_citation.py
│   │   │       ├─ audit_schema.py
│   │   │       ├─ collect_competitor_rss.py
│   │   │       ├─ generate_weekly_summary.py
│   │   │       ├─ generate_monthly_report.py
│   │   │       └─ detect_anomaly.py
│   │   ├─ services/                    ← 複数 Repository・コレクタを束ねるドメインサービス
│   │   │   ├─ wordpress_publisher.py
│   │   │   ├─ llms_txt_generator.py
│   │   │   ├─ schema_injector.py
│   │   │   ├─ resend_mailer.py
│   │   │   └─ csv_exporter.py
│   │   ├─ utils/
│   │   │   ├─ logger.py                ← structlog 設定
│   │   │   ├─ retry.py                 ← 指数バックオフデコレータ
│   │   │   ├─ encryption.py            ← Fernet ラッパー
│   │   │   └─ config_loader.py
│   │   ├─ worker/
│   │   │   └─ entrypoint.py            ← marketer-worker のエントリ(APScheduler 起動)
│   │   └─ tests/
│   │       ├─ unit/
│   │       ├─ integration/
│   │       └─ e2e/
│   └─ scripts/
│       ├─ create_admin_user.py
│       └─ seed_prompt_templates.py
├─ frontend/
│   ├─ package.json
│   ├─ vite.config.ts                   ← base: '/marketer/'
│   ├─ tsconfig.json
│   ├─ tailwind.config.js
│   ├─ index.html
│   ├─ src/
│   │   ├─ main.tsx
│   │   ├─ App.tsx                      ← React Router(basename="/marketer/")
│   │   ├─ pages/
│   │   │   ├─ LoginPage.tsx
│   │   │   ├─ DashboardPage.tsx
│   │   │   ├─ CitationMonitorPage.tsx
│   │   │   ├─ TargetQueriesPage.tsx
│   │   │   ├─ ContentsPage.tsx
│   │   │   ├─ CompetitorsPage.tsx
│   │   │   ├─ InquiriesPage.tsx
│   │   │   ├─ ReportsPage.tsx
│   │   │   └─ SettingsPage.tsx
│   │   ├─ components/
│   │   │   ├─ kpi/                     ← KpiCard, TrendBadge
│   │   │   ├─ charts/                  ← Recharts ラッパ
│   │   │   ├─ table/                   ← DataTable, Pagination
│   │   │   ├─ form/                    ← Input, Select, Field
│   │   │   ├─ layout/                  ← AppShell, Sidebar, Topbar
│   │   │   └─ feedback/                ← Toast, Alert, EmptyState
│   │   ├─ hooks/
│   │   │   ├─ useAuth.ts
│   │   │   ├─ useTenant.ts
│   │   │   └─ useApi.ts
│   │   ├─ api/
│   │   │   ├─ client.ts                ← axios/fetch ラッパ(TanStack Query 連携)
│   │   │   └─ <resource>.ts            ← endpoint 定義
│   │   ├─ types/                       ← 共有型(API レスポンス型)
│   │   └─ utils/
│   ├─ public/
│   └─ tests/
│       └─ e2e/                         ← Playwright
├─ deploy/
│   ├─ ecosystem.config.js              ← PM2 設定(marketer-api, marketer-worker)
│   ├─ nginx/marketer.conf              ← include 用 nginx スニペット
│   ├─ scripts/
│   │   ├─ install_postgres.sh          ← apt インストール手順スクリプト化
│   │   ├─ setup_db.sh                  ← DB / ロール / 拡張作成
│   │   ├─ backup.sh                    ← pg_dump 日次
│   │   ├─ restore.sh
│   │   └─ deploy.sh                    ← git pull → migrate → pm2 reload
│   ├─ systemd/
│   │   └─ marketer-backup.timer        ← systemd timer で backup.sh を発火(任意)
│   └─ .env.example
├─ .github/
│   └─ workflows/
│       ├─ ci.yml
│       └─ scheduled-watchdog.yml
├─ .gitignore
├─ .editorconfig
└─ README.md
```

### 3.1 主要ファイルの責務

- `backend/app/main.py`: FastAPI アプリ生成、ミドルウェア登録、ルータ集約。**ルートロジックを書かない**(各 router へ委譲)
- `backend/app/api/deps.py`: `get_current_user`, `get_current_tenant`, `get_db_session` を提供
- `backend/app/auth/middleware.py`: 受信 → JWT 検証 → `TenantContext` セット → DB 接続に `SET LOCAL app.tenant_id` 発行
- `backend/app/db/repositories/base.py`: 全 Repository が継承、`tenant_id` を引数に強制、内部で `WHERE tenant_id = :tid` を必ず付加(RLS と二重防御)
- `backend/app/ai_engine/providers/factory.py`: `get_for_use_case(tenant_id, use_case)` で適切な Adapter を返す、Adapter キャッシュを保持
- `backend/app/scheduler/scheduler.py`: APScheduler の初期化、各 job を `cron` トリガーで登録
- `backend/app/worker/entrypoint.py`: PM2 が起動するエントリポイント。スケジューラ起動 + ヘルスチェック用 HTTP(任意 3011)を立てる
- `frontend/src/App.tsx`: 認証ルート / 一般ルートを Router で振り分け

---

## 4. AI Provider 抽象化レイヤ設計

仕様書 2.2 / 設計指針 3 に従う完全版。Phase 2 での Adapter 追加を 3 ステップで完了させることが本設計の合格基準(指針 3.5)。

### 4.1 抽象基底クラスとデータ型

```python
# backend/app/ai_engine/providers/schemas.py
from pydantic import BaseModel
from typing import Any

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class ProviderResponse(BaseModel):
    text: str
    usage: TokenUsage
    provider: str
    model: str
    raw_response: dict[str, Any] | None = None
    finish_reason: str | None = None  # 'stop' | 'length' | 'safety' | ...

class ProviderError(Exception):
    """Provider 共通の呼び出しエラー。Adapter 層で個別例外を吸収"""
    def __init__(self, message: str, *, provider: str, retriable: bool = False, cause: Exception | None = None):
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable
        self.cause = cause


# backend/app/ai_engine/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Literal, Type
from pydantic import BaseModel

class AIProvider(ABC):
    name: str        # 'gemini' | 'claude' | 'openai' | 'perplexity'
    model: str

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        response_format: Literal["text", "json"] = "text",
        extra: dict | None = None,         # Provider 固有オプション(safety_settings 等)
    ) -> ProviderResponse: ...

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        *,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        extra: dict | None = None,
    ) -> BaseModel: ...

    @abstractmethod
    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        extra: dict | None = None,
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    def count_tokens(self, text: str) -> int: ...
```

### 4.2 Factory

```python
# backend/app/ai_engine/providers/factory.py
class AIProviderFactory:
    _registry: dict[str, type[AIProvider]] = {
        "gemini": GeminiAdapter,
        # Phase 2 で 1 行追加するだけ:
        # "claude": ClaudeAdapter,
        # "openai": OpenAIAdapter,
        # "perplexity": PerplexityAdapter,
    }

    @classmethod
    async def get_for_use_case(
        cls, tenant_id: UUID, use_case: AIUseCase
    ) -> AIProvider:
        # 1) DB の ai_provider_configs を tenant_id × use_case で検索
        # 2) 設定が無ければシステムデフォルト(Gemini Flash)を返す
        # 3) Adapter インスタンスを (provider, model, api_key_hash) でキャッシュ
        ...
```

### 4.3 GeminiAdapter の実装方針(Phase 1)

```python
# backend/app/ai_engine/providers/gemini_adapter.py
from google import genai
from google.genai import types as gtypes

class GeminiAdapter(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(self, system_prompt, user_prompt, *, max_tokens, temperature,
                       response_format, extra=None):
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json" if response_format == "json" else "text/plain",
            **(extra or {}),
        )
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model, contents=user_prompt, config=config,
            )
        except Exception as e:
            raise ProviderError(str(e), provider="gemini", retriable=_is_retriable(e), cause=e)
        return ProviderResponse(
            text=resp.text,
            usage=TokenUsage(
                input_tokens=resp.usage_metadata.prompt_token_count,
                output_tokens=resp.usage_metadata.candidates_token_count,
                total_tokens=resp.usage_metadata.total_token_count,
            ),
            provider="gemini",
            model=self.model,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
            finish_reason=str(resp.candidates[0].finish_reason) if resp.candidates else None,
        )

    async def generate_structured(self, system_prompt, user_prompt, schema, *,
                                  max_tokens, temperature, extra=None):
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            **(extra or {}),
        )
        resp = await self._client.aio.models.generate_content(
            model=self.model, contents=user_prompt, config=config,
        )
        return schema.model_validate_json(resp.text)

    async def stream(self, system_prompt, user_prompt, *, max_tokens, temperature, extra=None):
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            **(extra or {}),
        )
        async for chunk in self._client.aio.models.generate_content_stream(
            model=self.model, contents=user_prompt, config=config,
        ):
            if chunk.text:
                yield chunk.text

    def count_tokens(self, text: str) -> int:
        return self._client.models.count_tokens(model=self.model, contents=text).total_tokens
```

### 4.4 引用モニタとの分離(仕様書 6.3)

`backend/app/collectors/llm_citation/gemini_client.py` は **抽象レイヤを通さず**ハードコードで Gemini を Web grounding 付きで呼ぶ。理由は仕様書 4.1.3 の「ここで呼ぶ LLM は 2.2 とは別概念」に従うため。

API キーは別環境変数で分離可能:
- `MARKETER_GEMINI_API_KEY_AI_ENGINE`(AI Provider Adapter 用、無料枠を消費)
- `MARKETER_GEMINI_API_KEY_CITATION_MONITOR`(引用モニタ用、別 Google アカウント想定)

両者は `tenant_credentials` で `provider='gemini_ai_engine'` / `provider='gemini_citation_monitor'` として分けて保管(2.1 の enum で対応済み)。

### 4.5 プロンプト管理

- `ai_engine/prompts/<use_case>.md`(Markdown + Jinja2 プレースホルダ)が **本文の Source of Truth**
- DB の `prompt_templates` はファイルパス・バージョンを参照するだけ(本文は git 履歴で管理)
- バージョンアップ時は新しい行を `prompt_templates` に挿入し、`ai_provider_configs.prompt_template_id` を切替

### 4.6 Provider 追加時の作業(指針 3.5 の合格基準)

新 Adapter 追加で必要な変更:
1. `ai_engine/providers/<new>_adapter.py` を実装(150〜250 行想定)
2. `factory.py` の `_registry` に 1 行追加
3. `ai_provider` enum に値が既にあることを確認(2.1 で全 Provider 登録済み、追加不要)
4. 設定画面の選択肢を確認(`ai_provider` enum に紐付くため UI 自動反映)

ユースケース層・UI コード・DB スキーマには手を入れない。

### 4.7 フォールバック・リトライ

- Provider 呼び出しは `utils.retry` の指数バックオフデコレータで最大 3 回(仕様書 8.1)
- `ProviderError(retriable=True)` の場合のみリトライ
- 3 回失敗時、`ai_provider_configs.fallback_provider` が指定されていれば 1 回だけそちらにフォールバック
- それでも失敗したら `job_execution_logs` に記録し、管理者にメール通知

---

## 5. Phase 1 Week 別チケット詳細

26 チケット。各チケットには優先度(P0=最重要 / P1=必須 / P2=任意)、想定工数(時間)、依存先、受け入れ条件を付与。キセ 1 名で進める想定で 1 日 6 時間稼働 × 5 日 × 4 週 = 120 時間 + バッファ 20% = チケット合計上限 96 時間程度を目安。

### Week 1: 基盤(共通モジュール + 認証 + 配置 + 収集 1)

| # | チケット | 優先度 | 工数 | 依存 | 受け入れ条件 |
|---|---|---|---|---|---|
| W1-01 | リポジトリ初期化(`git init`、`.gitignore`、`.editorconfig`、README、CI スケルトン) | P0 | 2h | なし | `git push` が通る、CI で空テストが緑 |
| W1-02 | PostgreSQL 16 を VPS に apt インストール、`marketer` DB / ロール作成、拡張(`pgcrypto`)有効化 | P0 | 3h | W1-01 | `psql -U marketer -d marketer -c '\dx'` で pgcrypto が有効 |
| W1-03 | バックエンド土台(FastAPI + Uvicorn + SQLAlchemy + Alembic 初期化、main.py、settings.py) | P0 | 3h | W1-02 | `uvicorn app.main:app` が起動、`/healthz` が 200 |
| W1-04 | **共通モジュール**(logger / retry / encryption / config_loader / db.base / repositories.base / auth.middleware / tenant_context) | P0 | 8h | W1-03 | 各モジュールに pytest が緑、tenant_context が contextvar で分離 |
| W1-05 | 全テーブルの Alembic マイグレーション + RLS ポリシー一括設定 | P0 | 6h | W1-04 | `alembic upgrade head` 成功、テナント分離テスト緑 |
| W1-06 | 認証 API(login / logout / current_user)+ Argon2id + JWT + httpOnly Cookie | P0 | 5h | W1-04 | E2E でログイン → 認証必須 API へ到達できる |
| W1-07 | フロント雛形(Vite + Router basename + AppShell + LoginPage + DashboardPage stub) | P0 | 5h | W1-06 | `vite build` 成功、`/marketer/` でログイン画面が表示 |
| W1-08 | Nginx `/marketer/` 配置(`marketer.conf` 新規作成、`app` から include、`nginx -t` 通過) | P0 | 2h | W1-07 | `https://app.kiseeeen.co.jp/marketer/` で SPA が表示 |
| W1-09 | PM2 ecosystem 登録(`marketer-api` のみ、自動起動設定) | P0 | 2h | W1-08 | VPS 再起動後に PM2 が API を自動起動 |
| W1-10 | GSC コレクタ(OAuth 認証保管 + 週次取得 + DB 書き込み)+ ジョブ実行ログ | P0 | 8h | W1-04, W1-05 | 自社のクエリで GSC データが DB に格納される |
| W1-11 | GA4 コレクタ(同上) | P0 | 6h | W1-10 | 自社のセッション/CV データが DB に格納される |
| W1-12 | AI 引用モニタ(Layer)— ChatGPT/Claude/Perplexity/Gemini の 4 LLM クライアント + matcher | P0 | 10h | W1-04 | 各 LLM に対しクエリを投げて `citation_logs` に保存される |
| W1-13 | テナント分離 RLS テスト(指針 7.3)を pytest 化 | P0 | 3h | W1-05 | テナント A セッションでテナント B データが取れないことを CI で検証 |

**Week 1 合計: 63 時間**(目安 30 時間/週を超過。GSC/GA4/引用モニタは並列化やオプションで Week 2 へ繰越あり)。

### Week 2: Webhook + 構造化データ + AI 抽象レイヤ

| # | チケット | 優先度 | 工数 | 依存 | 受け入れ条件 |
|---|---|---|---|---|---|
| W2-01 | WordPress Webhook(記事公開トリガー)+ contents 台帳記録 | P0 | 4h | W1-04 | WP からの POST で `contents` 行が作成される |
| W2-02 | 構造化データ自動付与(Article + FAQPage + Person を生成、WP REST API で書き戻し) | P0 | 8h | W2-01 | 公開後 1 分以内に WP 記事の `<head>` に JSON-LD が入る |
| W2-03 | llms.txt 自動生成・WP デプロイ | P0 | 4h | W2-02 | サイトルートに最新の llms.txt が公開される |
| W2-04 | 構造化データ監査ジョブ(月次、`schema_audit_logs` 出力 + score 算出) | P0 | 5h | W2-02 | 既存記事に対しスコアと不足フィールド一覧が出る |
| W2-05 | AI Overviews 取得(SerpApi)— `aio_client.py` 実装、`tenant_credentials` で API キー保管 | P0 | 4h | W1-12 | AIO の引用結果が `citation_logs` に格納される |
| W2-06 | 競合 RSS 収集 | P1 | 3h | W1-04 | 設定された競合の最新記事が DB に蓄積される |
| W2-07 | **AI Provider 抽象化レイヤ**(`base.py`, `schemas.py`, `factory.py`, `mock_adapter.py`) | P0 | 5h | W1-04 | テストでモック差し替えが動く、Provider 追加 3 ステップを文書化 |
| W2-08 | **GeminiAdapter** 実装 + Web grounding なしの基本動作 | P0 | 5h | W2-07 | `generate` / `generate_structured` / `count_tokens` が動く |
| W2-09 | プロンプトテンプレ管理(`prompts/*.md` + Jinja2 ローダー + `prompt_templates` シード) | P0 | 3h | W2-07 | DB 経由でテンプレートが読まれ、変数差し込みが動く |
| W2-10 | テーマ提案ユースケース(動作確認用の最小実装)| P1 | 3h | W2-08, W2-09 | API で「テーマ提案して」を呼ぶと候補 5 件が返る |
| W2-11 | 問い合わせ Webhook(`inquiries` 受信)+ AI 構造化(`inquiry_structuring`) | P1 | 4h | W2-08 | フォーム送信で `inquiries` が作成、`ai_origin` が推定される |

**Week 2 合計: 48 時間**

### Week 3: AI 分析エンジン + ジョブ実行基盤

| # | チケット | 優先度 | 工数 | 依存 | 受け入れ条件 |
|---|---|---|---|---|---|
| W3-01 | APScheduler + `marketer-worker` PM2 登録、ジョブ実行ログ自動記録、リトライ・冪等性 | P0 | 5h | W1-09, W2-07 | 全ジョブが時刻通りに発火し `job_execution_logs` に成功/失敗が記録 |
| W3-02 | 月次レポート生成(Gemini 経由)+ Resend メール配信 + ダッシュボード履歴閲覧 | P0 | 8h | W3-01, W2-08 | 毎月 3 日 7:00 JST に生成、メールが届き、`reports` から読める |
| W3-03 | 週次サマリ生成 + メール配信 | P0 | 4h | W3-02 | 月曜 6:00 JST に短いサマリが届く |
| W3-04 | 引用機会分析(`citation_opportunity` ユースケース)+ 推奨アクション AI 生成 | P0 | 5h | W2-08 | 「競合は引用されているがクライアントは引用されていないクエリ」がリストされる |
| W3-05 | 異常検知トリガー(順位急落 / 引用率急減 / 到達不能)+ メール通知 | P0 | 5h | W1-10, W1-12 | 閾値を割ったら管理者にメール |
| W3-06 | E-E-A-T ギャップ分析ユースケース | P1 | 4h | W2-08 | 著者プロフィール不足項目をスコアと共に返す |
| W3-07 | コンテンツドラフト生成(`content_draft` ユースケース、Phase 1 ではテーマ採用 → ドラフト生成 → DB 保存まで) | P1 | 6h | W2-08 | API で「ドラフト生成」を呼ぶと Markdown が生成され `contents` に格納 |
| W3-08 | KPI 集計ジョブ(`kpi_logs` 日次 upsert)| P0 | 4h | W1-10, W1-11 | ダッシュボード用の日次 KPI が蓄積 |

**Week 3 合計: 41 時間**

### Week 4: ダッシュボード UI + 設定画面 + CSV エクスポート + 仕上げ

| # | チケット | 優先度 | 工数 | 依存 | 受け入れ条件 |
|---|---|---|---|---|---|
| W4-01 | ダッシュボードトップ(KPI カード群、推移グラフ、アラート、活動ログ) | P0 | 8h | W3-08 | 1 画面で全 KPI が把握できる |
| W4-02 | AI 引用モニタ画面(クエリ別テーブル、行展開、競合比較) | P0 | 6h | W2-05 | 仕様書 4.5.3 通りの表示 |
| W4-03 | ターゲットクエリ管理 + CSV インポート/エクスポート | P0 | 5h | W1-04 | UI で CRUD と CSV 取込ができる |
| W4-04 | コンテンツ管理 / 競合分析 / 問い合わせログ / レポート履歴 画面 | P0 | 8h | 各データ層 | 4 画面が機能する |
| W4-05 | 設定画面(基本情報・認証情報・著者プロフィール・通知・スケジュール・**AI Provider 設定**) | P0 | 8h | W1-06 | 全タブで CRUD が動く、AI Provider をプルダウンで切替可能 |
| W4-06 | CSV エクスポート全般(同期ダウンロード、Phase 1 範囲) | P1 | 3h | 各データ層 | KPI ログ・引用ログ・コンテンツ・問い合わせを CSV で取得可能 |
| W4-07 | エラーハンドリング・運用ログ整備・監視メトリクス公開(`/metrics` 任意) | P1 | 4h | W3-01 | UptimeRobot 相当の死活監視が可能 |
| W4-08 | 受け入れ基準(仕様書 17)を pytest / Playwright で自動化 | P0 | 6h | 全チケット | CI で受け入れ基準テスト緑 |
| W4-09 | デプロイスクリプト(`deploy/scripts/deploy.sh`)+ pg_dump 日次 cron | P0 | 3h | W1-09 | `git pull && ./deploy.sh` で migrate + reload が完結、cron でバックアップ生成 |

**Week 4 合計: 51 時間**

### 合計工数

| Week | 合計 | 備考 |
|---|---|---|
| Week 1 | 63h | 共通基盤と収集が重い。Week 2 へ一部繰越許容 |
| Week 2 | 48h | |
| Week 3 | 41h | |
| Week 4 | 51h | UI が多いが定型 |
| **総計** | **203h** | 1 日 6h × 5 日 × 4 週 = 120h を 70% 上回る |

→ **見直しポイント**: 1 名 4 週間で全 26 チケット P0/P1 完遂は厳しい。次の戦略のいずれかで吸収:

- (a) **P1 を Week 5 以降に繰越**(W2-06, W3-06, W3-07, W4-06, W4-07 = 22h)→ 残 181h、まだ 50% オーバー
- (b) **Phase 1 範囲の縮小**: W3-04(引用機会分析)、W3-05(異常検知)、W3-06(E-E-A-T 分析)、W3-07(ドラフト生成)を Phase 1.5 として 2 週追加
- (c) **AI 主導開発**(Claude Code に並列実装)で各チケットの実工数を 50〜60% 圧縮できる前提に立つ

→ **推奨は (c) 前提 +(b) のフォールバック**: Claude Code が並列で進めれば 4 週間で完遂可能。難航したら Phase 1.5(+2 週)に拡張する逃げ道を最初から確保。これは Phase 1 Week 1 終了時にキセが進捗を見て判定する。

---

## 6. 不確実性の選択肢(本書時点の確定)

設計合意セッションでの判断結果。再検討が必要になったら本書を更新。

| 論点 | 採用 | 理由 |
|---|---|---|
| AI Overviews 取得 | **SerpApi**(Phase 1)+ コレクタ層で抽象化 | 仕様書 16 章のリスク策に整合、最も安定 |
| 認証 | **自前 JWT + Argon2id + httpOnly Cookie** | 商材化での外部依存を避ける |
| 認可 | **DB の users.role + user_tenants(2 ロール)** | Phase 1 はロール 2 種で十分 |
| パスワードリセット | Phase 1 では管理者直リセット、UI は Phase 2 | 工数削減 |
| Nginx 配置 | **リバプロ + 静的配信** | 性能・実装シンプル |
| Postgres 配置 | **OS apt インストール** | B 案合意 |
| Postgres バージョン | **16** | RLS / JSONB の改善 |
| プロセス管理 | **PM2(`pm2-root` 配下)** | 既存運用と一貫 |
| 環境変数管理 | `.env` ファイル + 権限 0600 | Phase 1 シンプル、sops は Phase 2 |
| ジョブ基盤 | **APScheduler(常駐)** + GHA schedule で外形監視 | 仕様書 7.2 の二重監視要件を満たす |
| WordPress 連携 | **Application Password** | 仕様書記載 |
| メール | **Resend** | 仕様書記載 |
| 認証情報入力 UI | OAuth はリンク発行式、API キーはマスク入力 | 仕様書 10 章のフロー |

---

## 7. VPS 環境調査結果と配置案

詳細は `docs/vps_environment.md` を参照。要点:

- OS: Ubuntu 24.04.2 LTS、Nginx 1.24.0 / Python 3.12.3 / Node 22.18 が稼働
- メモリ 3.8 GiB / ディスク 99 GB(空き 47 GB)
- MySQL は既存サービス用に稼働、PostgreSQL は **本プロジェクトで apt 新規インストール**
- 既存サービスは PM2 で多数稼働、本プロジェクトもこの流儀に揃える
- ポート **3009** を本プロジェクトの API に確保(既存と衝突なし)
- Nginx の `/marketer/` プレフィックスは未使用、location 衝突なし
- 配置: `marketer.conf` を `sites-available` に新規作成し、メイン `app` から `include` する 1 行追加で済ませる

---

## 8. 想定リスクと対策(B 案前提で更新)

| # | リスク | 影響 | 対策 |
|---|---|---|---|
| R1 | LLM の API 仕様変更 | 引用モニタ停止 | 各 LLM クライアントを抽象化、変更時は 1 ファイル修正で済む構造 |
| R2 | Google AI Overviews 取得手段の不安定さ | LLMO 分析の一部欠損 | SerpApi / DataForSEO / 自前スクレイピングを Adapter で切替可能に(Phase 1 は SerpApi のみ) |
| R3 | クライアント認証情報の漏洩 | 信用失墜 | Fernet 暗号化 + 最小権限 + `audit_logs` 監査 + 0600 権限の `.env` |
| R4 | VPS 障害(ConoHa I/O hang 経験あり) | サービス全停止 | pg_dump 日次 + 別ディスクパス保管(Phase 1)→ B2 連携(Phase 2)、GHA scheduled-watchdog で外形監視 |
| R5 | Gemini の無料枠変更 | コスト増 | AI Provider 抽象化が前提なので 1 設定で別 Provider に即移行 |
| R6 | Gemini の処理品質不足 | レポート品質低下 | 用途別に Claude / GPT に切替、設定 UI で制御(Phase 2) |
| R7 | メモリ 3.8 GiB の逼迫 | OOM Kill | API + worker + Postgres で 500 MiB 追加。Vite ビルドはホスト直で実行、ピーク時はスワップ依存可。逼迫が常態化したら shared_buffers 縮小 / VPS 増強 |
| R8 | 既存 PM2 アプリへの影響 | 全体障害 | `marketer-*` は独立プロセス、既存と共有リソースなし。`pm2 reload marketer-api` で他に波及しないことを Week 1 で動作確認 |
| R9 | 既存 Nginx 設定(777 行)の誤編集 | 既存サイト全停止 | `marketer.conf` を別ファイル化、メイン `app` への変更は include 1 行のみ。設定変更前後で `nginx -t` 必須、`app.backup.YYYYMMDD` の慣習を踏襲 |
| R10 | Docker 不採用に伴うデプロイ再現性 | 別環境への移植困難 | `deploy/scripts/install_postgres.sh` `setup_db.sh` `deploy.sh` を整備、README に手順を明記。Phase 3 の商材化前に Docker 化を再検討 |
| R11 | 1 名 4 週間でのスコープ達成困難 | Phase 1 遅延 | 5 章で示した (a)(b)(c) の戦略。Week 1 終了時にキセが判定 |
| R12 | 競合の参入 | 商材化失敗 | キセの独自性(タイ製造業経営層経験、独自フレーム)で差別化、業種特化を売る |

---

## 9. 設計指針(design_guidelines.md)との整合確認

| 指針セクション | 本計画での対応 |
|---|---|
| 1. ファイル分割の原則(300 行推奨 / 500 行厳守) | 3 章のディレクトリ構成で機能を細分化、各 router・collector・adapter を独立ファイル化。長くなりがちな `gsc/runner.py` 等は `client.py` と分離 |
| 2.1 必須共通モジュール | W1-04 で 8 モジュール一括作成(logger / retry / encryption / config_loader / db.base / repositories.base / auth.middleware / tenant_context) |
| 3. AI Provider 抽象化レイヤ | 4 章で完全実装方針、3 ステップ追加可能性を W2-07 のチケット受け入れ条件に明記 |
| 4.1 Repository パターン | `db/repositories/base.py` が `tenant_id` 必須化、各リポジトリが継承 |
| 4.2 RLS 二重防御 | 2.3 の RLS ポリシー + アプリ層 `tenant_id` フィルタ、`FORCE ROW LEVEL SECURITY` で superuser でも逃れられない |
| 4.3 トランザクション境界 | 1 endpoint = 1 transaction、バッチはチェックポイント分割。LLM 呼び出し中は DB ロックを取らない |
| 5. コンテキスト管理 | Claude Code 利用者(キセ)が 1 セッション = 1 チケットで進める前提でチケットを 3〜10h 粒度に分解 |
| 7.1 各層のテストカバレッジ | W1-13(分離テスト)、W4-08(受け入れ基準自動化)で網羅 |
| 7.2 AI Provider モック | `mock_adapter.py` を W2-07 で実装、テストではこれを使用 |
| 7.3 マルチテナント分離テスト | W1-13 で必須化 |
| 8.1 構造化ログ | `utils/logger.py`(structlog)で `tenant_id` を contextvar から自動付与 |
| 8.2 ログに含めない情報 | API 認証情報・個人情報・AI 生成長文は別ストアまたはマスク |
| 11.3 LLM 呼び出しの非同期化 | API リクエスト中は LLM を呼ばず、バックグラウンドジョブに分離(月次レポート、ドラフト生成等) |

---

## 10. 環境変数一覧(`.env.example` 案)

```
# --- アプリ基本 ---
MARKETER_ENV=production
MARKETER_BASE_URL=https://app.kiseeeen.co.jp/marketer
MARKETER_API_PORT=3009

# --- DB ---
MARKETER_DB_DSN=postgresql+asyncpg://marketer:<password>@127.0.0.1:5432/marketer
MARKETER_DB_POOL_SIZE=5

# --- 暗号化 / JWT ---
MARKETER_FERNET_KEY=<32-byte url-safe base64>
MARKETER_JWT_SECRET=<random 64 chars>
MARKETER_JWT_TTL_MINUTES=60
MARKETER_JWT_REFRESH_TTL_DAYS=14

# --- システム共通 AI Provider キー(テナント別が無い場合のフォールバック)---
MARKETER_GEMINI_API_KEY_AI_ENGINE=
MARKETER_GEMINI_API_KEY_CITATION_MONITOR=
MARKETER_OPENAI_API_KEY=
MARKETER_ANTHROPIC_API_KEY=
MARKETER_PERPLEXITY_API_KEY=
MARKETER_SERPAPI_KEY=

# --- メール ---
MARKETER_RESEND_API_KEY=
MARKETER_MAIL_FROM=marketer@kiseeeen.co.jp
MARKETER_MAIL_NOTIFY_TO=admin@kiseeeen.co.jp

# --- バックアップ ---
MARKETER_BACKUP_DIR=/var/backups/marketer
MARKETER_BACKUP_RETENTION_DAYS=7
```

---

## 11. PostgreSQL 16 セットアップ手順(`deploy/scripts/install_postgres.sh` 内容)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Ubuntu 24.04 標準リポジトリの postgresql は 16.x
sudo apt-get update
sudo apt-get install -y postgresql-16 postgresql-contrib-16

sudo systemctl enable --now postgresql

# DB / ユーザー作成(対話なし、パスワードは事前に環境変数で渡す)
sudo -u postgres psql <<SQL
CREATE ROLE marketer LOGIN PASSWORD '${MARKETER_DB_PASSWORD}';
CREATE DATABASE marketer OWNER marketer;
\c marketer
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL

# localhost のみ bind(デフォルトのまま)、外部公開しない
echo "PostgreSQL 16 setup complete."
```

---

## 12. Nginx 設定(`deploy/nginx/marketer.conf` 雛形)

```nginx
# include from /etc/nginx/sites-enabled/app (HTTPS server block)

location /marketer/api/ {
    proxy_pass http://127.0.0.1:3009/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}

location /marketer/webhook/ {
    proxy_pass http://127.0.0.1:3009/webhook/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 5m;
}

location /marketer/ {
    alias /var/www/ai-web-marketer/frontend/dist/;
    try_files $uri $uri/ /marketer/index.html;
    add_header Cache-Control "public, max-age=3600";
}

# /marketer に末尾スラッシュなしでアクセスされたとき
location = /marketer {
    return 301 /marketer/;
}
```

メイン `app` への変更:

```nginx
# /etc/nginx/sites-enabled/app の HTTPS server { ... } 内末尾に 1 行追加
include /etc/nginx/sites-available/marketer.conf;
```

変更前に `nginx -t`、変更後に `systemctl reload nginx`。事故時の戻し方は `app.backup.YYYYMMDD_*` の既存習慣を踏襲。

---

## 13. PM2 ecosystem(`deploy/ecosystem.config.js` 案)

```js
module.exports = {
  apps: [
    {
      name: 'marketer-api',
      cwd: '/var/www/ai-web-marketer/backend',
      script: '/var/www/ai-web-marketer/backend/.venv/bin/uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 3009 --workers 2',
      env: { PYTHONUNBUFFERED: '1' },
      max_memory_restart: '600M',
      autorestart: true,
      watch: false,
      out_file: '/var/log/marketer/api.out.log',
      error_file: '/var/log/marketer/api.err.log',
    },
    {
      name: 'marketer-worker',
      cwd: '/var/www/ai-web-marketer/backend',
      script: '/var/www/ai-web-marketer/backend/.venv/bin/python',
      args: '-m app.worker.entrypoint',
      env: { PYTHONUNBUFFERED: '1' },
      max_memory_restart: '500M',
      autorestart: true,
      watch: false,
      out_file: '/var/log/marketer/worker.out.log',
      error_file: '/var/log/marketer/worker.err.log',
    },
  ],
};
```

`pm2-root` 配下に登録(`pm2 startup` は既存設定を流用、新規プロセスは `pm2 start /var/www/ai-web-marketer/deploy/ecosystem.config.js && pm2 save` で永続化)。

---

## 13.5 本番運用セットアップ手順(Phase 1 Week 4 完了後の追加メモ)

実装完了後、初回稼働で発見した運用上の手順を本節に追記する(Phase 2 開始前に
本書を v1.1 として更新する想定)。

### 13.5.1 LLM API キーの登録ルート

引用モニタの `_build_clients()` は **tenant_credentials を最優先** とし、
無ければ `.env`(`MARKETER_*_API_KEY`)にフォールバックする。
本番運用では tenant_credentials に登録するのが正解。`.env` だけ書いた場合も
動くが、テナント別の使い分けはできない(将来のマルチテナントで詰む)。

**初期セットアップの最短ルート**:

```bash
# 1. .env に各 API キーを設定
nano /var/www/ai-web-marketer/.env

# 2. PM2 に環境変数反映
sudo -u root pm2 reload marketer-api --update-env

# 3. .env から tenant_credentials へ一括コピー登録
cd /var/www/ai-web-marketer/backend
.venv/bin/python -m scripts.register_llm_credentials \
    --tenant-id <テナント UUID>
```

### 13.5.2 バックアップの注意

`backup.sh` は **postgres スーパーユーザーで pg_dump を実行する**こと。
marketer ロールは `FORCE ROW LEVEL SECURITY` 配下のテーブルで pg_dump が
QUERY FAILED を起こし、不完全ダンプが生成される。

cron は **pfkbn172 ユーザーの crontab** に登録し、ファイル所有権を統一する
(/var/backups/marketer は pfkbn172:pfkbn172 / 700 想定)。

リストア検証手順:
```bash
pg_restore -l /var/backups/marketer/marketer_daily_<曜日>.dump | head
# テーブル DDL と DATA 行が並べば壊れていない
```

### 13.5.3 Gemini Grounding の URL ラッパー対応

Gemini API の Grounding は引用 URL を `vertexaisearch.cloud.google.com/grounding-api-redirect/...`
ラッパー形式で返す。`gemini_client._resolve_wrapper_urls()` で HEAD/GET により
実 URL を取得 →(失敗時)`grounding_chunks[].web.domain` ヒントで合成 URL 生成、
というフォールバックを実装済み。HEAD 結果はクエリ単位でキャッシュし重複呼出しを抑制。

### 13.5.4 AI Overviews 取得の選択肢と現状(検証メモ)

仕様書 4.1.3 / 16 章で「SerpApi / DataForSEO / 自前 Headless スクレイピング」
の 3 系統を抽象化レイヤで持つ方針だが、Phase 1 自社運用で各案を検証した結果は
以下の通り。

| 案 | 月額 | 規約 | 安定性 | 現状 |
|---|---|---|---|---|
| **SerpApi** | $75〜 | ✅ 公式 | ✅ 安定 | 推奨だが高い |
| **DataForSEO** | ~$0.05〜10 | ✅ 公式 | ✅ 安定 | **中長期最有力** |
| **自前 Headless Chromium** | $0 | ⚠️ Google ToS グレー | ❌ Bot 検知で実用不可 | 棚上げ |

**自前 Headless 検証結果**: VPS の ConoHa データセンタ IP から Playwright で
`www.google.com` に検索クエリを投げると、即 `google.com/sorry/index` にリダイレクト
され Bot 検知メッセージ「お使いのコンピュータ ネットワークから通常と異なる
トラフィックが検出されました」が表示される。`navigator.webdriver` 偽装、
リアルな User-Agent / locale / timezone 指定では突破不可能。Google は IP の
ASN(自律システム番号)で「データセンタ帯」を識別しており、住宅 IP プロキシ
無しには対応困難。

**実装は `app/collectors/llm_citation/aio_headless_client.py` として残置**
(将来的に住宅 IP プロキシや別環境で動かす可能性を見越して)、
`runner.py` からは呼び出さない構成にしている。

**Phase 1 の AIO 運用**:
- SerpApi キー登録あり → SerpApi 経由で AIO 取得
- キー登録なし → AIO 列はスキップ(citation_logs に行を作らない)、
  ダッシュボードでも `—` 表示

**Phase 2 以降の改善方針**:
1. DataForSEO 契約 → `aio_client.py` と同パターンで Adapter 1 ファイル追加
2. SerpApi/DataForSEO どちらでも切替可能に(tenant_credentials 設定で選択)
3. Headless 案は完全に廃止するか、住宅 IP 契約とセットで再検討

---

## 14. 次の確認事項(キセに判断を求めること)

設計確定済み。**実装着手前にキセの最終 OK が欲しい論点**:

1. **本書の内容で着手していいか**(章立てに過不足がないか)
2. **GitHub リポジトリの作成タイミング**: 本書承認直後に `gh repo create kiseeeen/ai-webmarketer --private` で良いか? それとも先に Phase 1 Week 1 のチケット完了後にリモートを作るか?
3. **Phase 1 ターゲット完遂の判断**: 5 章で示した工数超過への戦略 (a)(b)(c) のうち、デフォルト想定としてどれを採るか(推奨は (c) Claude Code 並列実装前提 +(b) フォールバックで Phase 1.5 拡張余地)
4. **PM2 の所属**: `pm2-root` で OK か(推奨)、`pm2-react-dev` に揃えるか
5. **B2 バックアップの既存設定**: VPS 側で `rclone config` を確認し、設定があれば Phase 1 から流用、なければローカル世代管理のみで開始(Q11 の確認、Week 1 中にキセが確認)
6. **管理者初期ユーザー**: `scripts/create_admin_user.py` で初期 admin を 1 名作る想定。メールアドレスは `pfkbn172@gmail.com` で良いか?

---

*以上*
