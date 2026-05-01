# AIウェブマーケター SaaS

中小企業向け SEO/LLMO 運用自動化 SaaS。GSC・GA4・主要 5LLM の引用モニタを自動収集し、AI が月次/週次レポートと施策提案を生成する。

詳細仕様は `docs/` 配下を参照。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/ai_webmarketer_requirements_v2.1.md](docs/ai_webmarketer_requirements_v2.1.md) | 機能要件定義書(何を作るか) |
| [docs/ai_webmarketer_design_guidelines.md](docs/ai_webmarketer_design_guidelines.md) | 設計指針(どう作るか・どう作業するか) |
| [docs/ai_webmarketer_claude_code_handoff.md](docs/ai_webmarketer_claude_code_handoff.md) | Claude Code への指示書 |
| [docs/vps_environment.md](docs/vps_environment.md) | 既存 VPS 環境調査結果 |
| [docs/implementation_plan.md](docs/implementation_plan.md) | 実装計画(技術スタック、データモデル、Week 別チケット) |

## 構成概要

- 配置: `app.kiseeeen.co.jp/marketer/`(既存 VPS にパスベース同居)
- バックエンド: Python 3.12 + FastAPI + SQLAlchemy(async)
- フロント: React 18 + TypeScript + Vite + Tailwind CSS
- DB: PostgreSQL 16(apt インストール、RLS でテナント分離)
- 実行: PM2(`pm2-root` 配下、`marketer-api` / `marketer-worker`)
- リバプロ: 既存 Nginx に `marketer.conf` を `include` 追加

## ディレクトリ

```
ai-web-marketer/
├─ docs/         ← 仕様・設計・計画ドキュメント
├─ backend/      ← Python / FastAPI(Phase 1 で構築)
├─ frontend/     ← React + Vite(Phase 1 で構築)
├─ deploy/       ← Nginx / PM2 / バックアップスクリプト
└─ .github/      ← CI ワークフロー
```

## 開発フェーズ

- **Phase 1**(4 週間): 自社運用 MVP — 詳細は `docs/implementation_plan.md` の Week 別チケット参照
- **Phase 2**(4〜8 週間): 第 1 クライアント展開、Claude/OpenAI/Perplexity Adapter 追加
- **Phase 3**(2〜3 ヶ月): 商材化(ユーザー管理・課金・SLA)

## ライセンス

Internal use only(株式会社kiseeeen)
