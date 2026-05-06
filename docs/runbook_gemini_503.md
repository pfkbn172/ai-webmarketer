# Runbook: Gemini API 継続的 503 のワークアラウンド

最終更新: 2026-05-06
影響範囲: `daily_action_recommender` / `query_suggestion` / `content_brief` / `strategic_review` / `theme_suggestion` / `monthly_report` 等、Gemini を呼び出す全ユースケース

## 症状

```
ProviderError: 503 UNAVAILABLE.
{'error': {'code': 503, 'message': 'This model is currently experiencing
high demand. Spikes in demand are usually temporary. Please try again
later.', 'status': 'UNAVAILABLE'}}
```

`gemini_adapter._generate_with_retry` が 3 回までリトライ(指数バックオフ
2s/4s/8s)しても全て 503 を返すケースで発生する。Google 側の負荷波(特に
`gemini-2.5-flash` の混雑時)に依存し、一時的に数分〜数時間続く。

## 観測されたパターン(2026-05-06 19:00 JST 前後)

- 5 分間隔で 4 回試行 → すべて 503
- リトライ自動化されているのに `attempts=3` 全て 503 になることがある
- 個別ユースケース(content_brief 等)は通っていた時間帯の直後に発生

## 影響と判断

| 機能 | 影響 | 即時対応の必要性 |
|---|---|---|
| `recommend_daily_actions` (毎日 6:45) | ホーム画面のアクションが古いまま | 中(翌日朝には自然回復することが多い) |
| `monitor_citation` (毎日 4:00) | citation_logs の更新欠損 | 低(2-3日連続で起きない限りは問題なし) |
| `strategic_review` (手動実行) | 結果取得不能 | 低(時間を空けて再試行) |
| `query_suggestion` (手動) | 提案取得不能 | 低 |
| `content_brief` (手動) | ブリーフ生成不能 | **高**(オーナーが今やりたい操作の阻害) |
| `monthly_report` (毎月3日) | 月次レポート未生成 | 中(数時間遅延で済む) |

## 即時ワークアラウンド

### A. 自然回復を待つ(推奨)

通常は 30 分〜数時間で解消する。重要でなければ翌日のスケジューラ自動実行に任せる。

### B. 手動再実行(数分後に再試行)

5〜10分間隔で再試行する。例:

```bash
cd /var/www/ai-web-marketer/backend
.venv/bin/python -c "
import asyncio, uuid
from app.db.base import SessionLocal
from app.ai_engine.usecases.daily_action import recommend_daily_actions
from sqlalchemy import text

TENANT = uuid.UUID('7c59f23a-...')

async def main():
    async with SessionLocal() as s:
        await s.execute(text(f\"SET app.tenant_id = '{TENANT}'\"))
        actions = await recommend_daily_actions(s, TENANT)
        print(f'OK: {len(actions)} actions')

asyncio.run(main())
"
```

### C. 既存データで UI 検証を続行

LLM 呼出が必要なユースケースを除き、データ層・API・UI の検証は既存ストック
(`daily_actions` 既存行 / `content_briefs` 既存行 / `keyword_universe` 等)で
継続できる。本番動作確認のうち LLM 出力品質の確認だけが保留される。

### D. (将来) フォールバック Provider に切替

`tenant_credentials` に `claude` / `openai` キーを登録した上で、
`AIProviderFactory` をフォールバック対応に拡張する案。Phase 1 では未実装。
複数 Provider 設定済みのテナントなら `ai_provider_configs` テーブル経由で
特定ユースケースを Claude/OpenAI に向ける運用も可能。

## 監視と早期検知

- `job_execution_logs` の `status='failed'` を毎日 6:30 の `evaluate_alerts`
  が拾い、メール通知される(設定済みのテナントのみ)。
- ホーム画面の「システム健全性」セクションが直近 24 時間の失敗ジョブを表示。
- 連続 2 日 503 が続く場合は Gemini API のステータスページ
  (https://status.cloud.google.com/) を確認する。

## 根本対策候補(将来計画)

1. **モデル切替**: `gemini-2.5-flash` → `gemini-2.5-pro` (混雑度が違うことがある)
2. **フォールバック Provider**: Claude/OpenAI への自動切替
3. **キャッシュ層**: 同じプロンプトで一定時間内に呼ばれたら前回結果を返す
4. **時間分散**: 全テナントが朝同じ時刻に走るのを避けて 1 時間ぶん分散実行

これらは別計画で扱う。
