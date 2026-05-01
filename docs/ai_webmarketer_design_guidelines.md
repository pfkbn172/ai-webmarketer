# AIウェブマーケターSaaS 設計指針

株式会社kiseeeen 内部ドキュメント|2026年5月

---

## このドキュメントの位置づけ

本書は、Claude Codeが本プロジェクトを実装する際に従うべき**設計指針と運用ルール**をまとめたものです。仕様書(`ai_webmarketer_requirements_v2.1.md`)が「何を作るか」を定義するのに対し、本書は「**どう作るか・どう作業するか**」を定義します。

実装中、Claude Codeは作業前に本書の該当セクションを参照してください。判断に迷ったら本書を再読すること。

---

## 1. ファイル分割の原則

### 1.1 1ファイルの上限目安

| 種類 | 推奨上限 | 厳守上限 |
|---|---|---|
| Pythonモジュール | 300行 | 500行 |
| Reactコンポーネント | 200行 | 400行 |
| 設定ファイル(YAML/JSON) | 100行 | 200行 |
| プロンプトテンプレート | 100行 | 150行 |

**根拠**: Claude Code は長いファイルの編集で精度が顕著に落ちる。500行を超えるファイルは、ピンポイント編集時に意図しない箇所を巻き込む事故が増える。300行以下に保つと、ファイル全体を頭に入れたまま編集できる。

### 1.2 上限を超えそうになったときのアクション

ファイルが上限に近づいたら、**機能追加の前に必ず分割**する。「もう少し追加してから整理」は禁止。

分割パターン例:

- **責務分割**: 1つのクラス/モジュールが複数の責務を持っている → 責務ごとにファイル分割
- **共通化抽出**: 似た処理が複数箇所にある → utility に抽出
- **層分離**: API層・サービス層・データ層が混ざっている → 層ごとに分離

### 1.3 ディレクトリ構成の原則

機能ごとに垂直分割し、各ディレクトリは内部で完結する。Claude Codeに「特定機能だけを編集させる」ときに関連ファイルが少なくて済む。

```
backend/
├─ collectors/             # データ収集(Layer 1)
│   ├─ gsc/               # GSC関連だけで完結
│   ├─ ga4/
│   ├─ llm_citation/      # AI引用モニタ
│   └─ schema_audit/
├─ ai_engine/              # AI分析(Layer 2)
│   ├─ providers/         # AI Provider Adapter
│   ├─ usecases/          # ユースケース別の呼び出し
│   └─ prompts/           # プロンプトテンプレート
├─ webhook/                # Webhook(Layer 3)
├─ api/                    # REST API
├─ db/                     # DB層(repositories)
├─ auth/                   # 認証
├─ scheduler/              # スケジューラ
├─ utils/                  # 共通utility
└─ tests/

frontend/
├─ pages/                  # 画面単位
├─ components/             # 再利用コンポーネント
├─ hooks/                  # カスタムフック
├─ api/                    # APIクライアント
└─ utils/
```

### 1.4 命名規約

- ファイル名は **責務がひと目で分かる名前** にする(例: `gemini_adapter.py` であって `gemini.py` ではない)
- 抽象的な名前(`utils.py`, `helpers.py`, `manager.py`)を最上位に置かない。utilsの中で機能別に分割する(`utils/encryption.py`, `utils/retry.py` 等)
- 「中身を見ないと役割が分からない」名前は禁止

---

## 2. 共通化の対象

最初の数週間で必ず作る共通モジュール。これを後から作ろうとすると、各所にコピペコードが散らばって整理が困難になる。

### 2.1 必須共通モジュール(Week 1で作成)

| モジュール | 責務 |
|---|---|
| `utils/logger.py` | 構造化ログ(JSON形式)、tenant_idを自動付与 |
| `utils/retry.py` | 指数バックオフリトライ(デコレータ提供) |
| `utils/encryption.py` | API認証情報の暗号化・復号(Fernet等) |
| `utils/config_loader.py` | 環境変数・DB設定の読み込み |
| `db/base.py` | DB接続管理、トランザクション、tenant_idフィルタの強制 |
| `db/repositories/base.py` | Repositoryパターンの基底クラス |
| `auth/middleware.py` | 認証ミドルウェア(全エンドポイントで強制) |
| `auth/tenant_context.py` | リクエストごとのtenant_id解決 |

### 2.2 共通化の判断基準

「2回出てきたら抽出」のルールではなく、「**3回出てきたら、または将来確実に複数箇所で使われると分かったら抽出**」する。早すぎる共通化は柔軟性を失わせる。

ただし、以下は必ず共通化する:
- 認証・認可(セキュリティに関わるもの)
- DB接続(リソース管理に関わるもの)
- API認証情報の取り扱い(暗号化に関わるもの)
- マルチテナントのデータフィルタ(データ分離に関わるもの)

これらは1箇所にバグがあると全体が壊れるので、最初から共通化する。

### 2.3 共通化してはいけないもの

- 一度しか使われない処理を「将来使うかも」で共通化
- 似ているが本質的に違う処理(無理に共通化すると、引数で分岐が増えて読めなくなる)
- 業種固有のビジネスルール(クライアントごとに設定で分岐させる方が良い)

---

## 3. AI Provider抽象化レイヤの構造

仕様書セクション 2.2 に基づく具体実装方針。

### 3.1 ディレクトリ構成

```
ai_engine/
├─ providers/
│   ├─ base.py              # 抽象基底クラス AIProvider
│   ├─ gemini_adapter.py    # Phase 1で実装
│   ├─ claude_adapter.py    # Phase 2で実装
│   ├─ openai_adapter.py    # Phase 2で実装
│   ├─ perplexity_adapter.py # Phase 2で実装
│   └─ factory.py           # Provider生成のFactory
├─ usecases/
│   ├─ monthly_report.py    # 月次レポート生成
│   ├─ content_draft.py     # 記事ドラフト生成
│   ├─ theme_suggestion.py
│   ├─ compliance_check.py
│   ├─ inquiry_structuring.py
│   └─ eeat_analysis.py
├─ prompts/                 # プロンプトテンプレート(Markdown or YAML)
│   ├─ monthly_report.md
│   ├─ content_draft.md
│   └─ ...
└─ schemas/                 # 入出力のPydanticモデル
    └─ ...
```

### 3.2 抽象基底クラスの最低限のインターフェース

```python
class AIProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        response_format: Literal["text", "json"] = "text",
    ) -> ProviderResponse:
        ...

    @abstractmethod
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
    ) -> BaseModel:
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...
```

`ProviderResponse` には少なくとも以下を含める:
- `text`: 生成テキスト
- `usage`: トークン使用量(input / output / total)
- `provider`: プロバイダ名
- `model`: モデル名
- `raw_response`: デバッグ用の生レスポンス

### 3.3 Provider切替の仕組み

ユースケース層は Provider を直接知らない。Factory経由で取得する。

```python
# usecases/monthly_report.py
def generate_monthly_report(tenant_id: str, period: str):
    provider = AIProviderFactory.get_for_use_case(
        tenant_id=tenant_id,
        use_case="monthly_report"
    )
    # provider が Gemini か Claude かは Factory が DB を見て決める
    response = provider.generate(...)
```

`AIProviderFactory.get_for_use_case` は DB の `AIProviderConfig` テーブルを参照して、適切な Adapter を返す。

### 3.4 プロンプトテンプレートの管理

- プロンプトはコード内にハードコードしない。`prompts/*.md` 等のファイルで管理
- 変数差し込みは Jinja2 等のテンプレートエンジンを使う
- バージョン管理(プロンプト改善時に古いバージョンも残す)
- 各Providerで微調整が必要な場合は、ベース版から派生させる(完全に別ファイルにしない)

### 3.5 Provider追加時の作業

新しい Provider を追加するときの作業を、本指針が成功しているかの**テストケース**として使う。理想は以下の3ステップで完了すること:

1. `ai_engine/providers/new_adapter.py` を実装
2. `factory.py` に1行追加
3. 設定UIで選択肢を増やす

これ以外の場所(ユースケース層、UI、DBスキーマ)に手を入れる必要があれば、抽象化が漏れている。

---

## 4. データアクセス層

### 4.1 Repository パターン

API層・サービス層から直接 ORM を呼ばない。Repository を経由する。

```python
# db/repositories/target_query.py
class TargetQueryRepository(BaseRepository):
    def list_by_tenant(self, tenant_id: str) -> list[TargetQuery]:
        ...
    def create(self, tenant_id: str, query: str, ...) -> TargetQuery:
        ...
```

`BaseRepository` で tenant_id フィルタを強制する。

### 4.2 マルチテナント分離の二重チェック

論理的にはアプリ層でのフィルタで足りるが、コードバグでフィルタを忘れる事故を防ぐため、PostgreSQL の Row Level Security (RLS) も併用する。

```sql
ALTER TABLE target_queries ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON target_queries
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

リクエストごとに `SET app.tenant_id = '...'` を発行する。これでアプリ層のバグでも他テナントのデータは取れない。

### 4.3 トランザクション境界

- API endpoint 1つ = 1トランザクションを基本とする
- バッチ処理(Collector等)はチェックポイント単位で分割(失敗時に途中から再開できる)
- 長時間ロックを避ける(LLMのAPI呼び出し中にDB行をロックしない)

---

## 5. Claude Code のコンテキスト管理

### 5.1 1セッション=1チケットの原則

Claude Code に作業を依頼するときは、**1つのチケット(1〜4時間で終わる粒度)** に絞る。複数チケットをまたぐ依頼は性能劣化の主因。

良い例:
- 「`gsc_collector.py` を実装してください。仕様は `implementation_plan.md` のチケット #3 を参照」

悪い例:
- 「Week 1 のタスクを全部やってください」

### 5.2 コンテキストが膨らんできたら /clear

会話が長くなって Claude Code の応答が以下のような兆候を見せたら、即 `/clear` する:

- 直前に説明したことを忘れる
- 過去のコードと矛盾する提案をする
- 「ファイルが見つかりません」と言いながら実際は存在する
- 編集箇所を間違える(意図しないファイルを書き換える)

### 5.3 セッション再開時のコンテキスト復元

`/clear` 後は、最低限以下を渡してから再開する:

1. `docs/ai_webmarketer_requirements_v2.1.md` の関連セクション
2. `docs/implementation_plan.md` の該当チケット
3. `docs/ai_webmarketer_design_guidelines.md`(本書)の該当セクション
4. 直前まで作業していたファイル

これらを渡してから「続きから作業してください」と指示する。

### 5.4 Plan mode の活用

新しい機能を実装する前に、Claude Code に **Plan mode で計画を立てさせる**。

```
Plan mode で、チケット #5 の実装計画を立ててください。
- 編集するファイル
- 追加するファイル  
- テスト戦略
- 既存コードへの影響範囲
```

Plan の内容を確認してから実装に入る。これで「想定外の場所を書き換える」事故が減る。

### 5.5 TodoWrite の活用

複数ステップのタスクは、Claude Code の TodoWrite 機能で進捗を可視化する。Claude Code 自身が「今どこまでやったか」を見失うのを防ぐ。

---

## 6. Claude Code への指示出しのコツ

### 6.1 「完了しました」を信じない

Claude Code は楽観的に完了報告する傾向がある。以下を必ず確認する:

- 実際に動作確認したか(テスト実行 or 手動操作)
- エラーが出ていないか(ログを確認)
- 関連する既存テストがすべて通っているか
- 仕様書の受け入れ基準を満たしているか

完了報告を受けたら、必ず「動作確認の結果を見せてください」と返す。

### 6.2 仕様変更時は古いコードの削除を明示

機能を変更したり要件が変わったりしたとき、Claude Code は古いコードを残したまま新コードを追加する傾向がある。仕様変更時は次のように指示する:

```
要件Xを Y に変更します。
1. 旧Xを実装している箇所を全部リストアップしてください
2. それらをすべて削除または置換してください
3. 削除漏れがないか、grep で確認してください
```

### 6.3 git commit のタイミング

- チケット完了ごとに commit する
- 1コミット = 1論理変更
- Claude Code に勝手に commit させない(コミット前にキセが確認)
- commit message は規約(Conventional Commits等)に従う

### 6.4 リファクタリングと機能追加を混ぜない

「この機能を追加するついでに、隣のコードも整理しておいて」は事故のもと。リファクタリングは別チケットで行う。

### 6.5 不確実な実装の選択肢提示

実装方針が複数ありえるとき、Claude Code は1つを選んで実装に進もうとする。次のように指示する:

```
実装方針が複数ある場合は、選択肢を3つ程度提示してから、
それぞれのメリット・デメリットと推奨案を述べてください。
私の承認を待ってから実装に入ってください。
```

---

## 7. テスト戦略

### 7.1 各層のテスト

| 層 | テスト種類 | カバレッジ目標 |
|---|---|---|
| Repository層 | 単体テスト | 90%以上 |
| AI Provider Adapter | 単体テスト(モック化) | 80%以上 |
| ユースケース層 | 統合テスト | 70%以上 |
| API層 | 統合テスト | 80%以上 |
| Frontend | コンポーネントテスト+E2E | 主要動線のみ |

### 7.2 AI Provider のモック化

実装テストで実際のLLMを呼ぶとコストとレートリミットの問題が出る。`AIProviderMock` を用意して、テストではこれを使う。

### 7.3 マルチテナントの分離テスト

「テナントAのデータがテナントBから見えないこと」を必ずテストする。これは商材化の前提となる重要テストなので、Phase 1 から含める。

### 7.4 受け入れ基準の自動化

仕様書セクション17の受け入れ基準を、可能な限り自動テスト化する。Phase 1完了時に手動チェックではなく `pytest` 等で確認できる状態にする。

---

## 8. ロギングと監視

### 8.1 構造化ログ

すべてのログは JSON 形式の構造化ログで出力する。最低限のフィールド:

- `timestamp`
- `level`(INFO / WARNING / ERROR)
- `tenant_id`(リクエストコンテキストから自動付与)
- `request_id`(リクエスト追跡用)
- `module`(ログ出力元)
- `message`
- `extra`(任意の追加データ)

### 8.2 ログに含めない情報

- API認証情報(キー、トークン、パスワード)
- 個人情報(氏名、メール、電話番号)を平文で
- AI生成の長文レスポンス全体(別途専用ログに分離)

### 8.3 監視メトリクス

最低限、以下をメトリクスとして取得する:

- リクエスト数・エラー率(API層)
- ジョブ実行成功率(Scheduler)
- AI Provider呼び出しトークン使用量・料金
- AI引用モニタの取得成功率

---

## 9. リファクタリングのタイミング

### 9.1 必ずリファクタリングするタイミング

- ファイルが上限行数を超えそうになったとき(セクション 1.1)
- 同じパターンのコードが3箇所目に登場したとき
- 機能を追加するために既存コードを大きく書き換える必要があるとき

### 9.2 リファクタリング前にやること

- 既存テストが通っていることを確認
- リファクタリング対象を絞る(範囲拡大しない)
- 変更前の動作を記録(手動 or 自動テスト)

### 9.3 リファクタリング後にやること

- 既存テストがすべて通ることを確認
- 動作確認(リファクタリング前と同じ動作をすること)
- 不要になったコード・ファイルを削除

---

## 10. セキュリティ・データ取り扱い

### 10.1 認証情報の取り扱い

- 平文で扱える時間を最小化(復号 → 即座にAPI呼び出し → メモリから消去)
- ログ・エラーメッセージに認証情報を含めない
- 暗号化キーのローテーション手順を文書化(Phase 2 で実装)

### 10.2 マルチテナント分離

- セクション 4.2 の RLS 必須
- テスト(セクション 7.3)必須
- API層でも `tenant_id` を URL またはヘッダから明示的に受け取り、コンテキストに設定

### 10.3 監査ログ

設定変更・認証情報変更・テナント切替などのイベントは、別途監査ログテーブルに記録する。商材化時にコンプライアンス要件で必要になる。

---

## 11. パフォーマンスの考え方

### 11.1 早すぎる最適化を避ける

最初から「キャッシュ層を作る」「非同期処理にする」などの最適化を入れない。Phase 1 はシンプルに作り、計測してから最適化する。

### 11.2 ただしN+1問題は最初から避ける

ORM の N+1 問題だけは、最初から防ぐ。eager loading を活用する。Repository層でこれを意識する。

### 11.3 LLM呼び出しは非同期化

ユーザーリクエスト中に LLM を同期呼び出しすると、ダッシュボードの応答性が悪化する。LLM呼び出しはバックグラウンドジョブに分離する(月次レポート、ドラフト生成等)。

---

## 12. このドキュメントの更新

実装中に新たな知見が得られたら、本書を更新する。Claude Code が「設計指針に書かれていないが実装上必要だった判断」をした場合、その判断を本書に追記する。

---

## 13. Claude Code への指示テンプレート

実装中によく使う指示パターンをテンプレート化しておく。

### 13.1 新規実装の依頼

```
チケット #N の実装をお願いします。

## 参照
- 仕様書: docs/ai_webmarketer_requirements_v2.1.md セクション X.Y
- 計画書: docs/implementation_plan.md チケット #N
- 設計指針: docs/ai_webmarketer_design_guidelines.md セクション Z

## 進め方
1. まず Plan mode で実装計画を立ててください
2. 私が承認したら実装に入ってください
3. 完了したら動作確認結果を見せてください
4. 関連テストもすべて作成・実行してください
```

### 13.2 バグ修正の依頼

```
バグレポート: [現象]

期待動作: [期待]
実際動作: [現実]
再現手順: [手順]

## 進め方
1. 原因調査を最初にしてください、推測で修正に入らないこと
2. 原因が特定できたら、影響範囲をリストアップしてください
3. 修正方針を提示してください、私の承認を待ってください
4. 修正後、再現手順で動作を確認してください
5. 関連箇所に同じバグがないか grep で確認してください
```

### 13.3 リファクタリングの依頼

```
リファクタリング: [対象]

理由: [なぜ]
範囲: [どこまで]

## 制約
- 機能追加は含めないこと
- 公開API(関数シグネチャ・エンドポイント)は変えないこと
- 既存テストがすべて通ることを保証すること
- 変更前後で動作が同一であることを確認すること
```

### 13.4 セッション再開の指示

```
前回のセッションの続きです。

## 復元するコンテキスト
- 作業中のチケット: #N
- 完了済みチケット: #1, #2, ...
- 未完了タスク: ...

## 直前まで触っていたファイル
- src/...
- src/...

仕様書・計画書・設計指針は docs/ にあります。再読してから作業を続けてください。
```

---

*以上*
