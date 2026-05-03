/**
 * マニュアルページ。
 *
 * 初めて触る人が「このシステムは何をしてくれるのか / どこに何があるのか / いつデータが
 * 更新されるのか」を 1 画面で理解できるよう、章立てで網羅的に記載する。
 * 記述はコード内に直接埋め込む(将来 Markdown ファイル化や i18n 対応も可能だが、
 * Phase 1 はシンプルさ優先)。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

type Section = { id: string; title: string; body: React.ReactNode };

const SECTIONS: Section[] = [
  {
    id: 'overview',
    title: '1. このシステムは何をするのか',
    body: (
      <>
        <p>
          AIウェブマーケターは、中小企業向けに <b>SEO と LLMO</b>(LLM 最適化)の運用を
          自動化する SaaS です。「どのクエリで AI に引用されているか」「自社サイトのアクセス
          状況はどうか」「次月のコンテンツテーマは何にすべきか」を、人手をかけずに把握できる
          ようにします。
        </p>
        <p className="mt-3">
          このシステムが <b>勝手にやってくれること(データ収集)</b>:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li>毎週、Google Search Console と GA4 から自社サイトの数字を集めて整理する</li>
          <li>毎週、ChatGPT / Claude / Perplexity / Gemini / AI Overviews に主要クエリを
              投げて「自社が引用されたか」を記録する</li>
          <li>競合サイトの最新記事を RSS で追いかける</li>
          <li>毎月初めに、過去 30 日間の状況を要約した <b>月次レポート</b>を AI が生成して
              メールで届ける</li>
          <li>毎週月曜に、その週のハイライトを <b>週次サマリ</b>として AI が要約してメールで届ける</li>
          <li>新しい記事を WordPress に公開すると、自動で構造化データ(JSON-LD)を埋め込み、
              llms.txt も更新する(WordPress 連携設定済の場合)</li>
        </ul>
        <p className="mt-4">
          このシステムが <b>プロのマーケターのように考えてくれること(Phase 2)</b>:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li><b>違和感を検知する</b>: 数字の急変だけでなく「事業ステージとクエリ広域度の
              ミスマッチ」「全クエリで自社引用 0 が続く」など戦略的な違和感も検知し、
              ダッシュボードと戦略レビュー画面で警告</li>
          <li><b>事業文脈を踏まえてクエリを提案する</b>: 設定画面で入力した事業情報
              (拠点地域・独自性・弱点)を踏まえ、勝てる確度の高いクエリを 15〜20 本提案</li>
          <li><b>戦略レビューを生成する</b>: 「事業実態と数字の整合性評価」「構造的な発見
              3 つ」「次のアクション(根拠付き)」を AI が断言形式で出力</li>
          <li><b>戦略軸 A/B を比較する</b>: 「業種特化」と「地域特化」のような戦略選択を
              AI に推論評価させて勝者と推奨クエリを返す</li>
          <li><b>競合パターンを発見する</b>: 引用ログの全 URL から頻出ドメインを集計し、
              「未登録だが頻出 = 準競合候補」を可視化</li>
          <li><b>記事を改善する</b>: 既存記事を冒頭定義文・FAQ・E-E-A-T 等の 6 観点で
              評価し、LLMO 引用獲得のための具体的改善案を提示</li>
        </ul>
        <p className="mt-3">
          そして <b>あなたが見るところ</b> はこのダッシュボードと、メールで届くレポートの 2 つ。
          ターゲットクエリと著者プロフィールさえ初期設定すれば、あとはこのダッシュボードを
          週 1〜2 回開けば運用が回ります。
        </p>
      </>
    ),
  },
  {
    id: 'screens',
    title: '2. 画面の見方',
    body: (
      <>
        <h3 className="font-semibold">ダッシュボード(/)</h3>
        <p className="mt-1">
          1 画面で全体の KPI をまとめて表示します。
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li><b>AI 引用回数</b>: 過去 30 日に主要 LLM の回答に自社が引用された延べ回数</li>
          <li><b>オーガニックセッション</b>: GA4 の Organic Search 流入セッション数</li>
          <li><b>問い合わせ数</b>: 問い合わせ Webhook 経由で受信した件数(うち AI 起点を別表示)</li>
          <li><b>公開記事数</b>: 期間内に WordPress で公開した記事数</li>
          <li><b>セッション・引用推移</b>: セッション数(青)と AI 引用数(赤)の日次推移</li>
        </ul>

        <h3 className="mt-4 font-semibold">ターゲットクエリ(/queries)</h3>
        <p className="mt-1">
          引用モニタの監視対象クエリを管理します。1 テナントあたり最大 20 本まで(Phase 1)。
          ここに登録したクエリを毎週月曜 04:00 JST に主要 LLM へ投げて引用状況を記録します。
        </p>

        <h3 className="mt-4 font-semibold">AI 引用モニタ(/citations)</h3>
        <p className="mt-1">
          クエリ × LLM のクロス表で、過去 28 日の引用カウントを表示します。<br />
          セルの値は <code>自社引用 / 全モニタ回数</code>。
          <span className="text-destructive">赤(0/N)</span>は「モニタはしているが自社引用ゼロ」、
          <span className="text-foreground">通常色(1/N 以上)</span>は「引用あり」、
          <span className="text-muted-foreground">— </span>
          は「その LLM の API キー未契約 = 計測対象外」を意味します。
        </p>
      </>
    ),
  },
  {
    id: 'data-flow',
    title: '3. データの流れ・更新頻度',
    body: (
      <>
        <p>
          自動ジョブはすべてバックエンドの <code>marketer-worker</code> プロセスが
          APScheduler でスケジュールしています(時刻は JST)。
        </p>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-4">ジョブ</th>
              <th className="py-2 pr-4">頻度</th>
              <th className="py-2 pr-4">時刻</th>
              <th className="py-2">出力テーブル</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['GSC 収集', '週次', '月曜 03:00', 'gsc_query_metrics'],
              ['GA4 収集', '週次', '月曜 03:30', 'ga4_daily_metrics'],
              ['AI 引用モニタ', '週次', '月曜 04:00', 'citation_logs'],
              ['競合 RSS 収集', '週次', '月曜 05:00', 'competitor_posts'],
              ['週次サマリ生成 + メール', '週次', '月曜 06:00', 'reports (weekly)'],
              ['月次レポート生成 + メール', '月次', '毎月 3 日 07:00', 'reports (monthly)'],
              ['構造化データ監査', '月次', '毎月 1 日 04:30', 'schema_audit_logs'],
            ].map(([job, freq, time, out]) => (
              <tr key={job as string} className="border-b border-border/40">
                <td className="py-2 pr-4">{job}</td>
                <td className="py-2 pr-4 text-muted-foreground">{freq}</td>
                <td className="py-2 pr-4 text-muted-foreground">{time}</td>
                <td className="py-2 font-mono text-xs text-muted-foreground">{out}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="mt-4">
          ※ 月次レポートは GSC/GA4 のデータ確定遅延を吸収するため毎月 3 日に実行(1 日ではない)。
        </p>
        <p className="mt-2">
          ※ Webhook 系(WordPress 公開・問い合わせ受信)はスケジューリングではなく、
             外部からのイベント受信のたびに即時処理されます。
        </p>
      </>
    ),
  },
  {
    id: 'reports',
    title: '4. 届くレポートの中身',
    body: (
      <>
        <h3 className="font-semibold">月次レポート(毎月 3 日 07:00 JST)</h3>
        <p className="mt-1">過去 30 日間の総括。HTML メールで届く。構成:</p>
        <ol className="mt-2 list-decimal space-y-1 pl-6">
          <li>サマリ(全体 KPI と前月比)</li>
          <li>SEO 観点の分析</li>
          <li>LLMO 観点の分析(AI 引用率推移、引用機会、E-E-A-T ギャップ)</li>
          <li>コンテンツ施策の効果検証</li>
          <li>来月の推奨アクション(優先度付き 5〜10 項目)</li>
          <li>次月のコンテンツテーマ提案(5〜10 本)</li>
        </ol>

        <h3 className="mt-4 font-semibold">週次サマリ(毎週月曜 06:00 JST)</h3>
        <p className="mt-1">
          200 文字程度の短いハイライト + 来週の最優先アクション 1〜3 個。
          ダッシュボードを開く前に届くので、時間がない週でも要点だけは押さえられる。
        </p>

        <h3 className="mt-4 font-semibold">異常検知メール(随時)</h3>
        <p className="mt-1">
          以下を検知したら即時メール:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li>順位急落(同一クエリで前週 → 今週で平均順位が 10 以上悪化)</li>
          <li>引用率急減(自社引用率が前週比 50% 以下に低下)</li>
          <li>ジョブ失敗(API キー切れ・レート超過・サイト到達不能 等)</li>
        </ul>
      </>
    ),
  },
  {
    id: 'use-flow',
    title: '5. 日々の使い方(週次運用フロー)',
    body: (
      <>
        <p>
          このシステムを最大限に活かすための、推奨運用フローです。
          慣れたら 1 週間あたり 30 分〜1 時間で回せます。
        </p>

        <h3 className="mt-3 font-semibold">月曜朝(自動ジョブが回った後)</h3>
        <ol className="mt-2 list-decimal space-y-1 pl-6">
          <li>メールで届いた <b>週次サマリ</b>を読む(2 分)</li>
          <li>ダッシュボードを開いて KPI カードを確認(セッション数・AI 引用回数の推移)</li>
          <li>「AI 引用モニタ」画面を開いて、<span className="text-destructive">赤いセル</span>
              (引用ゼロ)が増えていないかチェック</li>
        </ol>

        <h3 className="mt-3 font-semibold">月初(月次レポート受信後)</h3>
        <ol className="mt-2 list-decimal space-y-1 pl-6">
          <li>月次レポートの <b>「来月の推奨アクション」</b> を読み、優先度高いものから着手</li>
          <li><b>「次月のコンテンツテーマ提案」</b> から 1〜3 本選んで、記事作成計画に反映</li>
          <li>必要なら「ターゲットクエリ」画面で監視対象を見直す</li>
        </ol>

        <h3 className="mt-3 font-semibold">記事を公開したとき</h3>
        <p className="mt-2">
          WordPress で公開すると Webhook が飛び、自動で:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li>構造化データ(Article + FAQPage + Person)が記事の <code>&lt;head&gt;</code> に挿入される</li>
          <li>llms.txt が最新の記事リストに更新される</li>
          <li>contents 台帳に記録され、翌週から GSC / GA4 / 引用モニタの対象になる</li>
        </ul>
        <p className="mt-2 text-muted-foreground">
          ※ WordPress 連携の事前設定が必要(REST API + Application Password)
        </p>

        <h3 className="mt-3 font-semibold">問い合わせが来たとき</h3>
        <p className="mt-2">
          問い合わせフォームから Webhook で送信されると、AI が業種・規模・意図を構造化して
          inquiries テーブルに記録されます。「AI 起点」かどうかも UTM パラメータと
          AI 推定で判定し、<b>ChatGPT / Claude / Perplexity / Gemini / AIO</b> のどれが
          きっかけかを記録します。
        </p>
      </>
    ),
  },
  {
    id: 'architecture',
    title: '6. システム構成(技術概要)',
    body: (
      <>
        <p>
          全体像を概念図で示します(エンジニア向け)。
        </p>
        <pre className="mt-3 overflow-x-auto rounded-md bg-muted p-3 text-xs leading-relaxed">{`
[Browser] ─ HTTPS ─▶ [Nginx (既存 VPS)]
                           │
                           ├─ /marketer/        → SPA 静的配信(React + Vite)
                           ├─ /marketer/api/    → FastAPI (PM2: marketer-api, port 3009)
                           └─ /marketer/webhook/→ FastAPI (同上)

[FastAPI] ◀─▶ [PostgreSQL 16] ←─ RLS で tenant_id 完全分離

[PM2: marketer-worker] ─ APScheduler ─▶ 各種ジョブ
        │                                       │
        ├─ GSC API / GA4 API(Google OAuth)─┘
        ├─ Gemini / OpenAI / Anthropic / Perplexity / SerpApi
        └─ WordPress REST API / Resend(メール)
`}</pre>

        <h3 className="mt-4 font-semibold">主要技術スタック</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>バックエンド: Python 3.12 + FastAPI + SQLAlchemy 2.x async + Alembic</li>
          <li>フロント: React 19 + TypeScript + Vite + Tailwind v3 + TanStack Query + Recharts</li>
          <li>DB: PostgreSQL 16(pgcrypto + pg_trgm 拡張、RLS で全テーブルテナント分離)</li>
          <li>認証: 自前 JWT(httpOnly Cookie)+ Argon2id</li>
          <li>暗号化: Fernet(API 認証情報を tenant_credentials に暗号化保管)</li>
          <li>プロセス管理: PM2(<code>pm2-root.service</code> 配下、systemd で永続化)</li>
          <li>AI Provider 抽象化レイヤ: Gemini / Claude / OpenAI / Perplexity を Adapter で
              切替可能(Phase 1 デフォルトは Gemini)</li>
        </ul>

        <h3 className="mt-4 font-semibold">バックアップ</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>毎日 04:00 JST に <code>pg_dump</code>(<code>postgres</code> スーパーユーザーで RLS バイパス)</li>
          <li>曜日別 7 世代ローテ + 月初は別途月次バックアップとして 13 ヶ月保管</li>
          <li>保管先: <code>/var/backups/marketer/</code>(将来的に Backblaze B2 同期予定)</li>
          <li>毎回 <code>pg_restore -l</code> でアーカイブ目次が読めるか検証</li>
        </ul>
      </>
    ),
  },
  {
    id: 'phase1-limits',
    title: '7. Phase 1 の制約と運用上の注意',
    body: (
      <>
        <h3 className="font-semibold">Phase 1 の範囲(自社運用 MVP)</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>テナントは 1 つ(自社のみ)</li>
          <li>ターゲットクエリは <b>20 本まで</b></li>
          <li>AI Provider は <b>Gemini のみ</b>(他 LLM は API キー契約後に追加可能)</li>
          <li>
            AI Overviews 取得は <b>SerpApi 契約必須</b>($75/月〜)。中長期は
            DataForSEO への切替で月 $0.05〜10 に圧縮予定。Phase 1 では未契約のため
            「AI 引用モニタ」画面の <code>aio</code> 列は <code>—</code> 表示
          </li>
        </ul>

        <h3 className="mt-4 font-semibold">Gemini Free Tier の制約</h3>
        <p className="mt-1 text-sm">
          Gemini API の無料枠は <b>1 日 20 リクエスト/モデル</b>。週次の引用モニタ
          (20 クエリ × 1 LLM = 20 リクエスト)で 1 日の枠を消費します。同日に手動で
          引用モニタを再実行したり月次レポートを試したりすると枠が枯渇します。
        </p>
        <p className="mt-2 text-sm">
          回避策:
        </p>
        <ul className="mt-1 list-disc space-y-1 pl-6 text-sm">
          <li>Gemini AI Engine 用と Citation Monitor 用で別 Google アカウントの API キーを使う(無料枠 2 倍)</li>
          <li>Gemini Pro プラン($30/月程度)に切替で枠拡大</li>
          <li>クエリ数を 10 本以下に減らす</li>
        </ul>

        <h3 className="mt-4 font-semibold">設定 UI が無い項目(現状は psql or スクリプト経由)</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>著者プロフィール(<code>author_profiles</code> テーブル)</li>
          <li>競合ドメイン(<code>competitors</code> テーブル)</li>
          <li>WordPress / Resend / SerpApi 等の認証情報(<code>tenant_credentials</code>)</li>
          <li>AI Provider × ユースケースの紐付け(<code>ai_provider_configs</code>)</li>
        </ul>
        <p className="mt-2 text-sm">
          → これらは Phase 2 以降で UI 化予定。当面はリポジトリ内のスクリプト
          (<code>backend/scripts/</code>)で操作できます。
        </p>
      </>
    ),
  },
  {
    id: 'troubleshoot',
    title: '8. 困ったときの確認方法',
    body: (
      <>
        <h3 className="font-semibold">数字が更新されない</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>VPS で <code>sudo -u root pm2 list</code> → marketer-worker が online か?</li>
          <li>VPS で <code>sudo -u root pm2 logs marketer-worker --lines 50</code> でエラーを見る</li>
          <li><code>job_execution_logs</code> テーブルで failed のジョブと error_text を確認</li>
        </ul>

        <h3 className="mt-4 font-semibold">引用モニタが skipped になる</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li>該当 LLM の API キーが <code>tenant_credentials</code> または <code>.env</code> に
              登録されているか確認</li>
          <li><code>scripts/register_llm_credentials.py</code> で <code>.env</code> から DB へ
              キーを再登録</li>
        </ul>

        <h3 className="mt-4 font-semibold">月次レポートのメールが来ない</h3>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
          <li><code>.env</code> の <code>MARKETER_RESEND_API_KEY</code> と
              <code>MARKETER_MAIL_NOTIFY_TO</code> が設定されているか</li>
          <li>Resend ダッシュボードで送信ログを確認(失敗の場合は SPF/DKIM 設定)</li>
          <li><code>reports</code> テーブルに HTML が保存されていれば、ダッシュボードからは
              読めるのでメール失敗だけが問題</li>
        </ul>

        <h3 className="mt-4 font-semibold">ログイン後すぐログアウトされる</h3>
        <p className="mt-2 text-sm">
          JWT の有効期限切れ。デフォルト 60 分。再ログインで OK。長くしたい場合は
          <code>.env</code> の <code>MARKETER_JWT_TTL_MINUTES</code> を上げる。
        </p>
      </>
    ),
  },
];

export default function ManualPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>マニュアル</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            初めての方向け。このシステムが何をするか、どう使うかを 1 ページで網羅。
          </p>
        </CardHeader>
        <CardContent>
          <nav className="grid gap-1 text-sm sm:grid-cols-2">
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                {s.title}
              </a>
            ))}
          </nav>
        </CardContent>
      </Card>

      {SECTIONS.map((s) => (
        <Card key={s.id} id={s.id} className="scroll-mt-20">
          <CardHeader>
            <CardTitle>{s.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm leading-relaxed">{s.body}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
