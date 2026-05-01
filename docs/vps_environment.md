# 既存VPS環境調査結果

株式会社kiseeeen 内部ドキュメント|2026年5月|`app.kiseeeen.co.jp`

本書は仕様書セクション19の「ステップ2: 既存VPS環境調査」に対応する成果物。
implementation_plan.md の前提資料として、Phase 1 の配置案・リソース見積もりを支える。

---

## 1. 基本情報

| 項目 | 内容 |
|---|---|
| OS | Ubuntu 24.04.2 LTS (Noble Numbat) |
| カーネル | Linux 6.8.0-110-generic (x86_64) |
| ホスト名 | `vm-da431602-13` |
| 公開ドメイン | `app.kiseeeen.co.jp`(443/80 で稼働、Let's Encrypt 想定) |
| 主要ユーザー | `pfkbn172`(uid 1001、Claude Code 実行ユーザー) |

## 2. リソース

| 項目 | 値 | 備考 |
|---|---|---|
| メモリ | 3.8 GiB total | available 約 2.9 GiB(調査時点) |
| スワップ | 4.0 GiB | 約 770 MiB 使用 |
| ルート FS(`/dev/vda2`) | 99 GB | 使用 48 GB / 空き 47 GB |
| `/var/www` 使用量 | 17 GB | 既存プロジェクト多数 |
| `/var/log` 使用量 | 1.2 GB | |

リソースは Phase 1(自社運用 1 テナント)では十分。商材化フェーズで複数テナントに広がるとメモリが先に逼迫する見込み。

## 3. 既存ソフトウェア

| ソフト | バージョン | 状態 |
|---|---|---|
| Nginx | 1.24.0 | 稼働中 |
| Python | 3.12.3 | システム標準 |
| Node.js | v22.18.0 | システム標準 |
| MySQL | 8.x | 稼働中(既存サービス用) |
| PostgreSQL | 未インストール | **本プロジェクトで apt 新規導入予定** |
| Docker | 未インストール | **本プロジェクトでは導入しない方針(B 案)** |
| PHP-FPM | 8.3 | 稼働中 |
| PM2(`pm2-root`, `pm2-react-dev`) | 6.0.8 | 稼働中、既存アプリ多数管理 |
| fail2ban | 稼働中 | |
| certbot | 稼働中(`/etc/cron.d/certbot`) | |
| ntpsec / postfix / unattended-upgrades | 稼働中 | |

## 4. 稼働中の主要アプリ(PM2 管理)

| プロセス | 種別 | ポート | パス |
|---|---|---|---|
| `ai-dx-api` | Node.js | 3001 | `/var/www/ai-dx-api/` |
| `auth-lucia-arctic` | Node.js | 3003 | `/var/www/auth-lucia-arctic/` |
| `socket-io` | Node.js | 3004 | `/var/www/socket-io/` |
| `excelike-table` | Node.js | 3005 | `/var/www/excelike-table/` |
| `DriveWatchWebSocket` | Node.js | 3006 | `/var/www/DriveWatchWebSocket/` |
| `hk/sheets-viewer` | Node.js | 3007 | `/var/www/hk/sheets-viewer/` |
| `Data-analytics`(uvicorn) | Python | 8003 | `/var/www/Data-analytics/` |
| `Data-analytics`(Next.js) | Node.js | 3008 | 同上 |
| `fuel-calc-server` | Node.js | 3010 | `/var/www/fuel-calc-server/` |
| `Playwright` | Python | 5000 | `/var/www/Playwright/` |
| `seo-check` | 不明 | 3100 | `/var/www/seo-check/` |
| MySQL | DB | 3306 | システム |

## 5. 空きポート

| ポート | 用途案 |
|---|---|
| **3009** | **本プロジェクトの API(FastAPI)に確保** |
| **3011** | 予備(worker メトリクス公開等) |
| 3101〜3199 | 予備 |
| 5432 | PostgreSQL のデフォルト(localhost のみ bind) |

3009 は連番空きで衝突なし。

## 6. Nginx 設定の現状

- 設定ファイル: `/etc/nginx/sites-available/app`(777 行、有効化済み)
- `server_name app.kiseeeen.co.jp;` は同ファイル内の HTTPS / HTTP ブロック双方に存在
- 80 → 443 リダイレクト構成済み
- 既存の `location` パスは多数(主要なもの):
  - `/ai-dx-consultant`, `/ai_dx_consultant`, `/auth/`, `/socket-io`, `/socket.io/`
  - `/excelike-table`, `/drivewatch-websocket`, `/hk/sheets-viewer`, `/playwright/`
  - `/web-design-agency`, `/tax-office`, `/manufacturing`, `/creative`, `/izakaya`
  - `/dashboard`, `/paddle-ocr`, `/selenium-indeed-scraper`, `/ai-tax-accountant`
  - `/local-ai-research-tool`, `/copain`, `/welfare-facility`, `/kitamura-koumuten`
  - `/uchidaya`, `/www`, `/crm-demo/`, `/data-analytics/`, `/outbound-manual`
  - `/particle-morphing`, `/timber-market`, `/pachinko-123`, `/law-office`
  - `/minesweeper`, `/fuel-calc`, `/referral2`, `/seo-check`, `/absorption-game`

**`/marketer/` プレフィックスは未使用**。本プロジェクトの location 追加で衝突する既存ルートはなし。

## 7. 既存運用パターンの観察

- 各アプリは `/var/www/<app名>/` 配下に独立配置
- Node.js / Python アプリは PM2 で管理(`pm2-root.service` で systemd 永続化)
- リバースプロキシは Nginx の `proxy_pass http://localhost:<port>` パターンで統一
- 静的サイトは `alias` で `/var/www/website/<name>/` を直接配信
- バックアップは sites-available 配下の `app.backup.YYYYMMDD_*` で nginx 設定スナップショットを残す習慣あり

## 8. 想定衝突・配慮点

| 論点 | 対応方針 |
|---|---|
| メモリ 3.8 GiB | 本システムは API + worker + Postgres で約 500 MiB 追加。Vite ビルドはホスト直で実施しピーク時にスワップ依存可 |
| MySQL と PostgreSQL の同居 | 別ポート(3306 vs 5432)、別データディレクトリ、別ユーザーで競合せず |
| Nginx 設定の巨大さ(777 行) | メイン `app` を編集せず、`marketer.conf` を別ファイルで作って `include` する形 |
| PM2 の root 起動 | 本プロジェクトも `pm2-root` 配下に乗せて運用一貫性を保つ |
| バックアップ | pg_dump 日次の cron を新規追加。B2 連携は既存 rclone 設定の有無を確認後に判断 |
| ConoHa VPS の I/O 障害事例 | データ永続性確保のため、pg_dump の世代管理(7 日 + 月次 1 年)を Phase 1 から実施 |

## 9. 配置案サマリ

```
[Browser]
   ↓ HTTPS
[Nginx /etc/nginx/sites-enabled/app]
   ├─ 既存 location 群(変更しない)
   └─ include /etc/nginx/sites-available/marketer.conf;  ← Phase 1 で追加
        ├─ /marketer/api/      → 127.0.0.1:3009 (FastAPI / PM2)
        ├─ /marketer/webhook/  → 127.0.0.1:3009 (同上)
        └─ /marketer/          → /var/www/ai-web-marketer/frontend/dist/(SPA 静的配信)

[PM2 (pm2-root)]
   ├─ marketer-api     : uvicorn app.main:app --host 127.0.0.1 --port 3009
   └─ marketer-worker  : APScheduler 常駐(収集ジョブ・AI バッチ処理)

[OS パッケージ]
   └─ PostgreSQL 16  : 127.0.0.1:5432, データ /var/lib/postgresql/16/main/
```

## 10. 次のアクション(implementation_plan.md で詳述)

1. PostgreSQL 16 を apt 経由でインストールし、本プロジェクト専用 DB / ユーザーを作成
2. `pfkbn172` ユーザー配下に Python venv を作って FastAPI 環境を構築
3. PM2 ecosystem ファイルで `marketer-api` / `marketer-worker` を登録
4. `/etc/nginx/sites-available/marketer.conf` を作成、`app` から `include` するよう 1 行追加
5. pg_dump の cron 登録(日次)
6. Phase 1 終了時、受け入れ基準セクション 17 の自動テスト化

---

*以上*
