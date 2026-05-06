/**
 * マーケター視点の包括的ダッシュボード。
 *
 * ブロック構成:
 *   1. 違和感アラート(高優先度のみ)
 *   2. KPI カード 4 種(前期間比 +%/-% 付き)
 *   3. 月次目標と進捗ゲージ + 編集
 *   4. セッション・引用推移グラフ
 *   5. 流入経路の内訳(GA4)
 *   6. クラスタ別 AI 引用率
 *   7. AI 引用ヒートマップ(主要 5 クエリ × LLM)
 *   8. 主要クエリ TOP 10(GSC)
 *   9. 競合パターン Top 3(準競合候補)
 *   10. Next Actions チェックリスト(AI 生成 + 手動編集)
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  fetchAiReferrals,
  fetchAlertRules,
  fetchDataSources,
  fetchAreaPerformance,
  fetchBrandSearch,
  fetchChannelBreakdown,
  fetchChannelCvr,
  fetchClusterCitation,
  fetchCompetitorContent,
  fetchCompetitorPatternsTop,
  fetchCvPaths,
  fetchFunnel,
  fetchHeatmap,
  fetchHourWeekdayHeatmap,
  fetchKeywordOpportunity,
  fetchNextActions,
  fetchObjectives,
  fetchPagePerformance,
  fetchPageRankDecay,
  fetchPageSpeed,
  fetchQueryRankChanges,
  fetchReferralsDay,
  fetchReferralsTop,
  fetchSearchIntent,
  fetchSeasonality,
  fetchTopQueries,
  generateNextActionsWithAi,
  replaceAlertRules,
  replaceNextActions,
  upsertObjectives,
  type AlertRule,
  type NextAction,
  type Objective,
} from '@/api/dashboard';
import { fetchKpiSummary, type KpiMetric, type KpiSummary } from '@/api/kpi';
import {
  CATEGORY_COLOR,
  CATEGORY_LABEL,
  createMarketingAction,
  deleteMarketingAction,
  fetchMarketingActions,
  updateMarketingAction,
  type MarketingAction,
  type MarketingActionCategory,
} from '@/api/marketing_actions';
import {
  createShareToken,
  fetchReports,
  reportPdfUrl,
  revokeShareToken,
} from '@/api/reports';
import { fetchAnomalies, type Anomaly } from '@/api/strategic';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { DataSourceBadge } from '@/components/ui/DataSourceBadge';
import { HelpHint } from '@/components/ui/HelpHint';
import { Input } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';

const CLUSTER_LABEL: Record<string, string> = {
  brand: 'ブランド',
  industry: '業種',
  service: 'サービス',
  local: 'ローカル',
  local_district_hq: '本拠地(平野区)',
  local_radius: '半径10km圏',
  geo_intent: '距離意図',
  industry_local: '地域×業種',
  competitive: '競合比較',
  use_case: 'ユースケース',
  feature: '機能',
  decision: '意思決定',
  pricing: '価格',
};

const LLM_ORDER = ['chatgpt', 'claude', 'perplexity', 'gemini', 'aio'];
const LLM_LABEL: Record<string, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  gemini: 'Gemini',
  aio: 'AIO',
};

/**
 * ブロック説明文の辞書。HelpHint に渡して項目意味と「何を見るべきか」を表示する。
 * - what: その指標が何を表しているか
 * - watch: 何を見るべきか / どんな状態が良い・悪いか
 */
const HELP: Record<string, { title: string; what: string; watch: string }> = {
  kpi_citation: {
    title: 'AI 引用回数',
    what: '主要 LLM(ChatGPT / Claude / Perplexity / Gemini / Google AIO)に対するモニタクエリで、自社サイト URL が回答内に含まれた回数。',
    watch: '増加傾向 = AIO/LLMO 対策が効いている。減少 = 競合が引用シェアを取っている可能性。',
  },
  kpi_sessions: {
    title: 'オーガニックセッション',
    what: 'GA4 計測のセッション総数(全チャネル合計)。サイト来訪セッション数の生数値。',
    watch: '前期間比 +/- と YoY が両方プラスかを確認。スパイク日があれば下の「参照元 Top」で原因特定。',
  },
  kpi_inquiries: {
    title: '問い合わせ数',
    what: 'inquiries テーブルに登録された期間内の問い合わせ件数(Web / Email / 電話 / AI 経由)。',
    watch: '増加が伸びていない場合は CVR を確認。CVR が下がっている=訴求やフォームの摩擦の問題。',
  },
  kpi_cvr: {
    title: 'リード CVR',
    what: '問い合わせ ÷ セッション。Web 集客のもっとも本質的な指標。',
    watch: '業種により目安は違うが 0.5〜2% 程度。下がっていれば LP / フォーム / オファーを見直す。',
  },
  kpi_contents: {
    title: '公開記事数',
    what: '期間内に公開ステータスになった記事の本数(WordPress webhook 経由で同期)。',
    watch: '記事公開ペースとセッション・引用回数の連動を確認。',
  },
  channels: {
    title: '流入経路',
    what: 'GA4 Organic Search / それ以外の 2 軸でセッション数を表示。',
    watch: '指名検索や AI 経由が増えていれば「ブランド認知」、Other が伸びていれば紹介・SNS など外部流入の手応え。',
  },
  channel_cvr: {
    title: 'チャネル別 CVR',
    what: 'AI Chat / Organic Search / Direct&Other ごとのセッション数 × 問い合わせ数 × CVR。問い合わせは GA4 ソースから按分。',
    watch: '「セッションが少ないが CVR は高い」チャネルは強化候補(例:AI 経由)。逆に「セッションは多いが CVR が低い」チャネルは LP 改善の優先度高。',
  },
  ai_referrals: {
    title: 'AI 経由の流入',
    what: 'ChatGPT / Claude / Perplexity / Gemini / Copilot などの AI チャットから sessionSource として返ってきた来訪セッション。',
    watch: 'AI 引用回数と AI 流入セッションの両方が伸びていれば「LLM が自社を答えている」状態。引用は出るが流入が増えない=記事のクリック誘引が弱い。',
  },
  cluster_citation: {
    title: 'クラスタ別 AI 引用率',
    what: 'ターゲットクエリのクラスタ(ブランド/業種/サービス/ローカル等)ごとに「自社が引用された / 全モニタ数」の比率。',
    watch: 'ブランドは 80% 以上が望ましい。業種・ローカルは 30〜50% が目安。0% のクラスタはコンテンツ強化の優先度高。',
  },
  referrers: {
    title: '参照元 Top',
    what: 'GA4 の sessionSource × sessionMedium 別合計セッション。「a0b.biz / referral」のようにメール経由まで識別可能。',
    watch: '見覚えのない referrer がスパイクしていたら拡散イベント発生。下の日付ピッカーで時間別に詳細展開して原因を特定。',
  },
  cv_paths: {
    title: '流入チャネル別 CV(按分概算)',
    what: '流入チャネル別のセッション数と「日次セッション割合で按分した」問い合わせ数。本格的な multi-touch attribution は GA4 BigQuery 連携が必要。',
    watch: 'あくまで概算なので「どのチャネルが優勢か」の傾向把握用に使う。',
  },
  brand_search: {
    title: 'ブランド検索ボリューム',
    what: 'GSC の query にブランド名(社名・ドメイン)が含まれるクエリの月次 表示・クリック数。',
    watch: '右肩上がり = ブランド認知が拡大。横ばいや下落 = PR / 露出が弱まっている可能性。',
  },
  hour_weekday: {
    title: '曜日 × 時間帯ヒートマップ',
    what: '指定期間内の (曜日 × 時間帯) ごとの合計セッション数。色が濃いほどアクセスが多い。',
    watch: 'ピーク時間帯にあわせて記事公開・SNS 投稿・メール送信を行うと露出効率が上がる。',
  },
  seasonality: {
    title: '季節性ヒートマップ',
    what: '(月 × 曜日) ごとの平均セッション数。年間の周期性を把握する。',
    watch: '繁忙月や閑散月のパターンが見えれば、コンテンツ投入や広告予算の配分計画に使う。',
  },
  trend: {
    title: 'セッション・引用推移',
    what: '日次 / 週次 / 月次のセッション・AI 引用・問い合わせ数の推移。7 日移動平均と異常値(±3σ)もハイライト。施策タイムラインの色マーカーが重なる。',
    watch: '異常値の赤丸がついた日は下の「参照元 Top」で原因特定。施策マーカーとセッションの連動が見えれば施策効果の証拠。',
  },
  next_actions: {
    title: 'Next Actions',
    what: '戦略レビュー(Gemini)が提案した次の行動候補。手動で追加・編集・完了管理ができるチェックリスト。',
    watch: '「AI 提案で更新」を押すと最新の戦略レビュー結果からアクションを再生成する。',
  },
  page_performance: {
    title: '記事/ページ別パフォーマンス',
    what: 'ページごとのセッション・GSC クリック / 表示 / CTR / 平均順位 / AI 引用回数を一覧化。',
    watch: 'CTR が赤(上位なのに低い) → タイトル/ディスクリプション要改善。緑(低順位なのに高 CTR) → 順位を上げる伸びしろあり。',
  },
  page_rank_decay: {
    title: '順位下落ページ',
    what: '直近 14 日と前 30 日のページ平均順位を比較。下落幅が大きい順に表示。',
    watch: '上位だったページが落ちているなら情報の鮮度切れや競合上昇が原因。リライト候補。',
  },
  page_speed: {
    title: 'Core Web Vitals',
    what: '主要ページの PageSpeed Insights 計測結果(LCP / CLS / INP / Performance Score)。Mobile / Desktop 別。',
    watch: 'LCP > 2.5s, CLS > 0.1, INP > 200ms は赤信号。SEO 評価とユーザー体験の両方に影響。',
  },
  funnel: {
    title: 'コンバージョン漏斗',
    what: 'inquiries.status の遷移(新規 → 商談中 → 受注 / 失注)と件数・金額。CV 率と平均受注単価も併記。',
    watch: '「商談化」までで止まっているなら営業フォロー強化、「受注」までで止まっているなら提案内容の見直し。',
  },
  query_rank_changes: {
    title: 'クエリ順位変動 Top 10',
    what: '直近 14 日と前 14 日でクエリ別平均順位の差分。プラスは順位上昇、マイナスは下落。',
    watch: '上昇クエリ = 自然に伸びているテーマ → 関連記事を増やす。下落クエリ = 早期リライトで原因解消。',
  },
  citation_heatmap: {
    title: 'AI 引用ヒートマップ',
    what: 'priority 上位 5 クエリ × LLM 別の「自社引用回数 / 全モニタ回数」のマトリクス。',
    watch: 'ChatGPT は出るが Perplexity は出ないなど LLM 別の弱点が見える。0/X の枠が多い LLM は出力傾向に合わせた記事構造が必要。',
  },
  search_intent: {
    title: '検索意図の分布',
    what: 'GSC クエリを「取引型 / ナビ型 / 情報収集型 / その他」に自動分類し、表示・クリック・順位を集計。',
    watch: '取引型クエリの順位を 1 桁台に乗せると CV につながりやすい。情報収集型は自然流入の入口として量を取りに行く。',
  },
  area_performance: {
    title: 'エリア別パフォーマンス',
    what: '本拠地 / 半径10km圏 / 距離意図 / 地域×業種 / 競合比較 など、地域系クラスタ別の表示・クリック・順位・引用率。',
    watch: '本拠地クラスタの引用率が低ければ MEO / Google Business Profile / 構造化データ強化が効く。',
  },
  keyword_opportunity: {
    title: 'キーワード機会マトリクス',
    what: '表示回数 × 平均順位 × 引用率の組み合わせから「次に狙うべき」キーワードを推奨アクション付きで提示。',
    watch: 'win = 1〜3 位 + 引用も多い(維持)、optimize = 4〜10 位(改善で勝ち取る)、create = 表示多いが順位なし(新規記事)。',
  },
  top_queries: {
    title: '主要クエリ TOP 10',
    what: 'GSC のクエリ別 表示・クリック・CTR・平均順位の上位 10。',
    watch: '表示が多いのにクリックが少ない=タイトル・ディスクリプション要改善。順位が良いのに表示数が少ない=検索ボリュームが小さい。',
  },
  competitor_top: {
    title: '準競合候補 Top 3',
    what: 'AI 引用ログから「自社が引用されたモニタクエリで、同じ回答に出ていた他ドメイン」を集計。',
    watch: 'ここに繰り返し出るドメインは「AI が自社と一緒に答える参考先」。彼らの記事構成・スキーマを研究対象に。',
  },
  competitor_content: {
    title: '競合に引用された記事',
    what: '競合 RSS フィードから取得した最近の競合記事のうち、AI 引用ログに登場したもの。',
    watch: '引用回数の多い競合記事 = AI が「答えに使う構造」を持っている。タイトル・見出し・要約構造を分解する。',
  },
  alerts: {
    title: 'アラート設定',
    what: 'セッション急落・AI 引用急落・問い合わせゼロ日数・異常値検知の閾値を設定し、メール / Slack で通知を受ける。',
    watch: '「異常値検知」をオンにしておくと推移グラフの赤丸日が自動で通知される。',
  },
  reports: {
    title: '月次/週次レポート',
    what: '生成済みの自動レポートと、外部共有用のトークン URL の発行・失効。',
    watch: 'クライアント共有用の URL は期限・閲覧履歴で管理する。',
  },
  marketing_actions: {
    title: '施策タイムライン',
    what: '記事公開 / SEO 改善 / 広告 / プレス / イベント などのマーケ施策を時系列で記録。推移グラフのマーカーに反映される。',
    watch: 'スパイクや急落が起きた日に施策がなかったか、ここで遡って因果を確認する。',
  },
  objectives: {
    title: '月次目標と進捗',
    what: '当月の目標値(セッション / AI 引用 / 問い合わせ / 公開記事)に対する進捗率。',
    watch: '月の中盤までで 50% を超えていない指標は要対策。下の「目標を編集」で目標自体を見直す。',
  },
};

function H({ k }: { k: keyof typeof HELP }) {
  const h = HELP[k];
  return (
    <HelpHint
      title={h.title}
      body={
        <>
          <div>
            <span className="font-medium text-foreground">何を表すか:</span> {h.what}
          </div>
          <div>
            <span className="font-medium text-foreground">何を見るべきか:</span>{' '}
            {h.watch}
          </div>
        </>
      }
    />
  );
}

/**
 * データソース一覧を一度だけ取得して各ブロックで参照するためのフック。
 * 5 分間キャッシュ。同じキーは React Query が共有する。
 */
function useDataSourceMap() {
  const { data } = useQuery({
    queryKey: ['dashboard', 'data-sources'],
    queryFn: fetchDataSources,
    staleTime: 5 * 60_000,
  });
  return data ?? {};
}

/** カード見出しの右に置くデータソースバッジ。`ks` で参照するソースキーを指定。 */
function DS({ ks }: { ks: string[] }) {
  const map = useDataSourceMap();
  const sources = ks.map((k) => map[k]).filter(Boolean);
  if (sources.length === 0) return null;
  return <DataSourceBadge sources={sources} />;
}

/**
 * カード見出し共通行: タイトル + ?ヘルプ を左、データソースバッジを右に並べる。
 * 既存の `<div className="flex items-baseline gap-2">` を置き換えるラッパー。
 */
function HeaderRow({
  title,
  help,
  ds,
}: {
  title: React.ReactNode;
  help?: keyof typeof HELP;
  ds?: string[];
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
      <div className="flex items-baseline gap-2">
        <CardTitle>{title}</CardTitle>
        {help && <H k={help} />}
      </div>
      {ds && <DS ks={ds} />}
    </div>
  );
}

/** Recharts XAxis 用の縦 3 行ティック(YYYY / MM / DD)。狭い幅でも読める。 */
function DateTick(props: { x?: number; y?: number; payload?: { value?: string } }) {
  const { x = 0, y = 0, payload } = props;
  const raw = payload?.value ?? '';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  const [yyyy, mm, dd] = m ? [m[1], m[2], m[3]] : [raw, '', ''];
  return (
    <g transform={`translate(${x},${y + 8})`}>
      <text textAnchor="middle" fill="hsl(var(--muted-foreground))" fontSize={10}>
        <tspan x={0} dy={0}>
          {yyyy}
        </tspan>
        <tspan x={0} dy={12}>
          {mm}
        </tspan>
        <tspan x={0} dy={12}>
          {dd}
        </tspan>
      </text>
    </g>
  );
}

/** トレンドグラフ用カスタム Tooltip。施策があれば一覧で表示する。 */
function TrendTooltip(props: {
  active?: boolean;
  label?: string;
  payload?: Array<{
    name?: string;
    value?: number | string;
    color?: string;
    payload?: {
      actions?: {
        id: string;
        title: string;
        category: MarketingActionCategory;
        description: string | null;
      }[];
    };
  }>;
}) {
  if (!props.active || !props.payload?.length) return null;
  const data = props.payload[0]?.payload;
  const actions = data?.actions ?? [];
  return (
    <div
      className="rounded-md border border-border bg-card px-3 py-2 text-xs text-card-foreground shadow-lg"
      style={{ minWidth: 180 }}
    >
      <div className="mb-1 font-semibold">{props.label}</div>
      {props.payload
        .filter((p) => p.name !== '施策')
        .map((p, i) => (
          <div key={i} className="flex justify-between gap-4">
            <span style={{ color: p.color }}>{p.name}</span>
            <span className="tabular-nums">{p.value}</span>
          </div>
        ))}
      {actions.length > 0 && (
        <div className="mt-2 border-t border-border pt-1">
          <div className="mb-1 text-[10px] text-muted-foreground">施策 {actions.length} 件</div>
          {actions.map((a) => (
            <div key={a.id} className="mb-1">
              <div
                className="font-medium"
                style={{ color: CATEGORY_COLOR[a.category] }}
              >
                ● {a.title}
                <span className="ml-1 text-[10px] opacity-70">
                  [{CATEGORY_LABEL[a.category]}]
                </span>
              </div>
              {a.description && (
                <div className="text-[10px] text-muted-foreground">{a.description}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DeltaBadge({ delta, label }: { delta: number | null; label: string }) {
  if (delta === null || delta === undefined) {
    return <span className="text-xs text-muted-foreground">{label} —</span>;
  }
  const positive = delta >= 0;
  const cls = positive
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-rose-600 dark:text-rose-400';
  const sign = positive ? '+' : '';
  return (
    <span className={`text-xs font-medium ${cls}`}>
      {label} {sign}
      {delta.toFixed(1)}%
    </span>
  );
}

function KpiCard({
  label,
  metric,
  hint,
  coverageSince,
  rate,
  rateHint,
  helpKey,
}: {
  label: string;
  metric?: KpiMetric;
  hint?: string;
  coverageSince?: string | null;
  /** 率系 KPI(CVR 等)。指定すると metric の代わりに % で表示する。 */
  rate?: { value: number; delta_pct: number | null; yoy_pct: number | null };
  rateHint?: string;
  /** ヘルプ ? アイコンに表示する HELP 辞書のキー */
  helpKey?: keyof typeof HELP;
}) {
  // YoY を出すには 1 年以上の蓄積が必要
  const hasYearOfData = coverageSince
    ? Date.now() - new Date(coverageSince).getTime() >= 365 * 24 * 3600 * 1000
    : false;

  const isRate = rate !== undefined;
  const display = isRate
    ? rate?.value !== undefined
      ? `${rate.value.toFixed(2)}%`
      : '—'
    : (metric?.value ?? '—');
  const deltaPct = isRate ? (rate?.delta_pct ?? null) : (metric?.delta_pct ?? null);
  const yoyPct = isRate ? (rate?.yoy_pct ?? null) : (metric?.yoy_pct ?? null);

  return (
    <Card>
      <CardHeader className="p-4 pb-1">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
          {helpKey && <H k={helpKey} />}
        </div>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="text-2xl font-semibold tabular-nums sm:text-3xl">{display}</div>
        <div className="mt-1 flex flex-col gap-0.5">
          {(rateHint || hint) && (
            <span className="text-[11px] text-muted-foreground">{rateHint ?? hint}</span>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <DeltaBadge delta={deltaPct} label="前期間比" />
            {hasYearOfData ? (
              <DeltaBadge delta={yoyPct} label="YoY" />
            ) : (
              <span className="text-xs text-muted-foreground" title="1 年分のデータが揃うと YoY を表示します">
                YoY 蓄積中
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AnomalyBanner() {
  const { data = [] } = useQuery({
    queryKey: ['strategic', 'anomalies'],
    queryFn: fetchAnomalies,
  });
  const high = data.filter((a: Anomaly) => a.severity === 'high');
  if (high.length === 0) return null;
  return (
    <Card className="border-destructive/50 bg-destructive/5">
      <CardContent className="pt-6">
        <div className="flex items-start gap-3">
          <span className="rounded bg-destructive px-2 py-1 text-xs text-destructive-foreground">
            ⚠ {high.length} 件の違和感
          </span>
          <div className="flex-1 space-y-1">
            {high.slice(0, 3).map((a: Anomaly, i: number) => (
              <p key={i} className="text-sm">
                <b>{a.kind}</b>: {a.detail}
              </p>
            ))}
            <Link to="/strategic" className="text-xs text-primary hover:underline">
              戦略レビュー画面で確認 →
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ObjectivesBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'objectives'],
    queryFn: fetchObjectives,
  });

  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="月次目標と進捗"
          help="objectives"
          ds={['ga4_daily', 'citation', 'inquiries', 'contents']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">右側の編集欄から目標を設定してください。</p>
        ) : (
          <ul className="space-y-3">
            {data.map((o: Objective) => (
              <li key={o.key}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="text-muted-foreground">{o.label}</span>
                  <span className="tabular-nums">
                    <b>{o.current}</b> / {o.target}
                    <span className="ml-2 text-xs text-muted-foreground">
                      ({o.progress_pct.toFixed(0)}%)
                    </span>
                  </span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, o.progress_pct)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ObjectivesEditor() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({
    queryKey: ['dashboard', 'objectives'],
    queryFn: fetchObjectives,
  });
  const initial = (key: string) => data.find((d: Objective) => d.key === key)?.target ?? 0;

  const [sessions, setSessions] = useState('');
  const [citations, setCitations] = useState('');
  const [inquiries, setInquiries] = useState('');
  const [contents, setContents] = useState('');

  useEffect(() => {
    if (data.length === 0) return;
    setSessions(String(initial('monthly_sessions') || ''));
    setCitations(String(initial('monthly_citations') || ''));
    setInquiries(String(initial('monthly_inquiries') || ''));
    setContents(String(initial('monthly_contents') || ''));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.length]);

  const mut = useMutation({
    mutationFn: () =>
      upsertObjectives({
        monthly_sessions: Number(sessions) || 0,
        monthly_citations: Number(citations) || 0,
        monthly_inquiries: Number(inquiries) || 0,
        monthly_contents: Number(contents) || 0,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard', 'objectives'] }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>目標を編集</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Field label="月間セッション目標">
          <Input
            type="number"
            min={0}
            value={sessions}
            onChange={(e) => setSessions(e.target.value)}
            placeholder="例: 1000"
          />
        </Field>
        <Field label="月間 AI 引用回数目標">
          <Input
            type="number"
            min={0}
            value={citations}
            onChange={(e) => setCitations(e.target.value)}
            placeholder="例: 50"
          />
        </Field>
        <Field label="月間問い合わせ目標">
          <Input
            type="number"
            min={0}
            value={inquiries}
            onChange={(e) => setInquiries(e.target.value)}
            placeholder="例: 5"
          />
        </Field>
        <Field label="月間記事公開目標">
          <Input
            type="number"
            min={0}
            value={contents}
            onChange={(e) => setContents(e.target.value)}
            placeholder="例: 8"
          />
        </Field>
        <Button onClick={() => mut.mutate()} disabled={mut.isPending} className="w-full">
          {mut.isPending ? '保存中…' : '保存'}
        </Button>
        {mut.isSuccess && <p className="text-xs text-emerald-600">保存しました</p>}
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function ChannelBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'channels', days],
    queryFn: () => fetchChannelBreakdown(days),
  });
  const total = data.reduce((s, d) => s + d.sessions, 0);
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="流入経路"
          help="channels"
          ds={['ga4_daily']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">GA4 データがまだありません。</p>
        ) : (
          <ul className="space-y-2">
            {data.map((d) => {
              const pct = total > 0 ? (d.sessions / total) * 100 : 0;
              return (
                <li key={d.channel}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{d.channel}</span>
                    <span className="tabular-nums">
                      {d.sessions} ({pct.toFixed(0)}%)
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary/70"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ChannelCvrBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'channel-cvr', days],
    queryFn: () => fetchChannelCvr(days),
  });
  const totalSessions = data.reduce((s, r) => s + r.sessions, 0);
  const totalInquiries = data.reduce((s, r) => s + r.inquiries, 0);
  const overallCvr = totalSessions > 0 ? totalInquiries / totalSessions : null;
  // CVR の最大値を 100% として横棒に伸ばす(視覚比較しやすいように)
  const maxCvr = Math.max(...data.map((r) => r.cvr ?? 0), 0.0001);
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="チャネル別 CVR"
          help="channel_cvr"
          ds={['ga4_daily', 'ga4_ai_referral', 'inquiries']}
        />
        <p className="mt-1 text-[11px] text-muted-foreground">
          全体 CVR:
          <span className="ml-1 font-medium text-foreground">
            {overallCvr === null ? '—' : `${(overallCvr * 100).toFixed(2)}%`}
          </span>
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : totalSessions === 0 ? (
          <p className="text-sm text-muted-foreground">GA4 データがまだありません。</p>
        ) : (
          <ul className="space-y-2">
            {data.map((r) => {
              const pct = r.cvr !== null ? (r.cvr / maxCvr) * 100 : 0;
              return (
                <li key={r.channel}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{r.channel}</span>
                    <span className="tabular-nums text-xs text-muted-foreground">
                      {r.inquiries}/{r.sessions}
                      <span className="ml-2 font-medium text-foreground">
                        {r.cvr === null ? '—' : `${(r.cvr * 100).toFixed(2)}%`}
                      </span>
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-emerald-500/70"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function AiReferralsBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'ai-referrals', days],
    queryFn: () => fetchAiReferrals(days),
  });
  const total = data.reduce((s, d) => s + d.sessions, 0);
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="AI 経由の流入"
          help="ai_referrals"
          ds={['ga4_ai_referral']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            ChatGPT / Claude / Perplexity / Gemini / Copilot からの流入はまだ検出されていません。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((d) => {
              const pct = total > 0 ? (d.sessions / total) * 100 : 0;
              return (
                <li key={d.label}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>
                      {d.label}{' '}
                      <span className="text-xs text-muted-foreground">({d.source_host})</span>
                    </span>
                    <span className="tabular-nums">
                      {d.sessions} ({pct.toFixed(0)}%)
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-emerald-500/70"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ReferralDayDetail({ targetDate }: { targetDate: string }) {
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'referrals-day', targetDate],
    queryFn: () => fetchReferralsDay(targetDate),
  });
  if (isPending) {
    return <p className="text-xs text-muted-foreground">読み込み中…</p>;
  }
  if (!data || data.daily_breakdown.length === 0) {
    return <p className="text-xs text-muted-foreground">この日のデータはありません。</p>;
  }
  // 時間別を hour ごとにグループ化
  const byHour: Record<number, typeof data.hourly_rows> = {};
  for (const r of data.hourly_rows) {
    (byHour[r.hour] ??= []).push(r);
  }
  const hours = Object.keys(byHour)
    .map(Number)
    .sort((a, b) => a - b);
  return (
    <div className="space-y-3 rounded border border-border bg-muted/30 p-3 text-xs">
      <div>
        <div className="mb-1 font-medium">{data.target_date} の合計: {data.total_sessions} セッション</div>
        <table className="w-full">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-0.5">参照元</th>
              <th className="py-0.5">media</th>
              <th className="py-0.5 text-right">セッション</th>
            </tr>
          </thead>
          <tbody>
            {data.daily_breakdown.map((r, i) => (
              <tr key={i} className="border-t border-border">
                <td className="py-0.5 max-w-[18rem] truncate">{r.source}</td>
                <td className="py-0.5 text-muted-foreground">{r.medium}</td>
                <td className="py-0.5 text-right tabular-nums">{r.sessions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hours.length > 0 && (
        <div>
          <div className="mb-1 font-medium">時間別内訳</div>
          <div className="space-y-1.5">
            {hours.map((h) => (
              <div key={h}>
                <div className="text-muted-foreground">{h}:00 台</div>
                <ul className="ml-3 list-disc">
                  {(byHour[h] ?? [])
                    .filter((r) => r.sessions > 0)
                    .map((r, i) => (
                      <li key={i}>
                        {r.source} <span className="text-muted-foreground">/ {r.medium}</span> ──{' '}
                        <span className="tabular-nums font-medium">{r.sessions}</span>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ReferrersBlock({ days }: { days: number }) {
  const [openDate, setOpenDate] = useState<string | null>(null);
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'referrals', days],
    queryFn: () => fetchReferralsTop(days, 15),
  });
  const total = data?.total_sessions ?? 0;
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = (() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  })();
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="参照元 Top 15"
          help="referrers"
          ds={['ga4_referral', 'ga4_referral_hourly']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : !data || data.rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            ga4_referral_daily にデータがまだありません(初回 GA4 ジョブ後に表示)。
          </p>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">参照元(source)</th>
                  <th className="py-1">media</th>
                  <th className="py-1 text-right">セッション</th>
                  <th className="py-1 text-right">割合</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r, i) => {
                  const pct = total > 0 ? (r.sessions / total) * 100 : 0;
                  return (
                    <tr key={i} className="border-t border-border">
                      <td className="py-1 max-w-[18rem] truncate">{r.source}</td>
                      <td className="py-1 text-xs text-muted-foreground">{r.medium}</td>
                      <td className="py-1 text-right tabular-nums">{r.sessions}</td>
                      <td className="py-1 text-right tabular-nums text-muted-foreground">
                        {pct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground">スパイク日詳細:</span>
              <input
                type="date"
                className="h-7 rounded border border-input bg-background px-2 text-xs"
                value={openDate ?? ''}
                max={yesterday}
                onChange={(e) => setOpenDate(e.target.value || null)}
              />
              <button
                className="h-7 rounded border border-input bg-background px-2 text-xs hover:bg-muted"
                onClick={() => setOpenDate(yesterday)}
              >
                昨日
              </button>
              {openDate && openDate !== today && (
                <button
                  className="h-7 rounded border border-input bg-background px-2 text-xs hover:bg-muted"
                  onClick={() => setOpenDate(null)}
                >
                  閉じる
                </button>
              )}
            </div>
            {openDate && <div className="mt-2"><ReferralDayDetail targetDate={openDate} /></div>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ClusterCitationBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'cluster-citation', days],
    queryFn: () => fetchClusterCitation(days),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="クラスタ別 AI 引用率"
          help="cluster_citation"
          ds={['citation']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">引用モニタの結果がまだありません。</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">クラスタ</th>
                <th className="py-1 text-right">自社引用</th>
                <th className="py-1 text-right">合計</th>
                <th className="py-1 text-right">引用率</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.cluster_id} className="border-t border-border">
                  <td className="py-1">{CLUSTER_LABEL[c.cluster_id] ?? c.cluster_id}</td>
                  <td className="py-1 text-right tabular-nums">{c.self_cited}</td>
                  <td className="py-1 text-right tabular-nums">{c.total}</td>
                  <td className="py-1 text-right tabular-nums">{(c.rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function HeatmapBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'heatmap', days],
    queryFn: () => fetchHeatmap(days, 5),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="AI 引用ヒートマップ(主要 5 クエリ × LLM)"
          help="citation_heatmap"
          ds={['citation']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">引用モニタの結果がまだありません。</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-1 pr-2">クエリ</th>
                  {LLM_ORDER.map((p) => (
                    <th key={p} className="py-1 px-2 text-center">
                      {LLM_LABEL[p]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1 pr-2 align-top">
                      <div className="font-medium">{row.query_text}</div>
                      {row.cluster_id && (
                        <div className="text-[10px] text-muted-foreground">
                          {CLUSTER_LABEL[row.cluster_id] ?? row.cluster_id}
                        </div>
                      )}
                    </td>
                    {LLM_ORDER.map((p) => {
                      const cell = row.cells.find((c) => c.llm_provider === p);
                      const total = cell?.total ?? 0;
                      const cited = cell?.self_cited ?? 0;
                      const ratio = total > 0 ? cited / total : 0;
                      const bg =
                        total === 0
                          ? 'bg-muted/40 text-muted-foreground'
                          : ratio >= 0.5
                            ? 'bg-emerald-500/30'
                            : ratio > 0
                              ? 'bg-amber-500/30'
                              : 'bg-rose-500/20';
                      return (
                        <td key={p} className="px-1 py-1 text-center">
                          <div
                            className={`mx-auto rounded px-2 py-1 tabular-nums ${bg}`}
                            title={`${cited}/${total}`}
                          >
                            {total === 0 ? '—' : `${cited}/${total}`}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TopQueriesBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'top-queries', days],
    queryFn: () => fetchTopQueries(days, 10),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="主要クエリ TOP 10(GSC)"
          help="top_queries"
          ds={['gsc_query']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">GSC データがまだありません。</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">クエリ</th>
                <th className="py-1 text-right">表示</th>
                <th className="py-1 text-right">CL</th>
                <th className="py-1 text-right">CTR</th>
                <th className="py-1 text-right">順位</th>
              </tr>
            </thead>
            <tbody>
              {data.map((q, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="py-1 truncate max-w-[18rem]">{q.query_text}</td>
                  <td className="py-1 text-right tabular-nums">{q.impressions}</td>
                  <td className="py-1 text-right tabular-nums">{q.clicks}</td>
                  <td
                    className="py-1 text-right tabular-nums font-medium"
                    title={
                      q.ctr === null || q.avg_position === null
                        ? undefined
                        : q.avg_position <= 3 && q.ctr < 0.05
                          ? '上位表示なのに CTR が低い: タイトル/ディスクリプション要改善'
                          : q.avg_position > 10 && q.ctr > 0.05
                            ? '低順位なのに CTR 良好: 順位を上げる伸びしろあり'
                            : undefined
                    }
                  >
                    {q.ctr === null ? (
                      '—'
                    ) : (
                      <span
                        className={
                          q.avg_position !== null && q.avg_position <= 3 && q.ctr < 0.05
                            ? 'text-rose-600 dark:text-rose-400'
                            : q.avg_position !== null && q.avg_position > 10 && q.ctr > 0.05
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : ''
                        }
                      >
                        {(q.ctr * 100).toFixed(1)}%
                      </span>
                    )}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {q.avg_position === null ? '—' : q.avg_position.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function CompetitorTopBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'competitor-top', days],
    queryFn: () => fetchCompetitorPatternsTop(days),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="準競合候補 Top 3"
          help="competitor_top"
          ds={['citation']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            AI 引用ログから検出された他ドメインがまだありません。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((d) => (
              <li key={d.domain} className="flex items-baseline justify-between text-sm">
                <div>
                  <div className="font-medium">{d.domain}</div>
                  <div className="text-xs text-muted-foreground">{d.label}</div>
                </div>
                <span className="tabular-nums text-xs">{d.count}回</span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 text-right">
          <Link to="/strategic" className="text-xs text-primary hover:underline">
            戦略レビューで確認 →
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

function NextActionsBlock() {
  const qc = useQueryClient();
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'next-actions'],
    queryFn: fetchNextActions,
  });
  const [draft, setDraft] = useState('');

  const saveMut = useMutation({
    mutationFn: (items: NextAction[]) => replaceNextActions(items),
    onSuccess: (data) => qc.setQueryData(['dashboard', 'next-actions'], data),
  });
  const aiMut = useMutation({
    mutationFn: () => generateNextActionsWithAi(),
    onSuccess: (data) => qc.setQueryData(['dashboard', 'next-actions'], data),
  });

  const toggle = (id: string) => {
    const next = data.map((a) =>
      a.id === id ? { ...a, completed: !a.completed } : a,
    );
    saveMut.mutate(next);
  };
  const remove = (id: string) => {
    saveMut.mutate(data.filter((a) => a.id !== id));
  };
  const add = () => {
    if (!draft.trim()) return;
    const next: NextAction[] = [
      ...data,
      { id: crypto.randomUUID(), text: draft.trim(), rationale: null, completed: false },
    ];
    saveMut.mutate(next);
    setDraft('');
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <HeaderRow title="Next Actions" help="next_actions" />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => aiMut.mutate()}
            disabled={aiMut.isPending}
          >
            {aiMut.isPending ? 'AI 生成中…' : 'AI で再生成'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            まだ Next Actions が登録されていません。「AI で再生成」を押すか、下の入力欄から追加してください。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((a) => (
              <li
                key={a.id}
                className="flex items-start gap-2 rounded border border-border/60 p-2"
              >
                <input
                  type="checkbox"
                  checked={a.completed}
                  onChange={() => toggle(a.id)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className={a.completed ? 'text-sm line-through text-muted-foreground' : 'text-sm'}>
                    {a.text}
                  </div>
                  {a.rationale && (
                    <div className="text-xs text-muted-foreground">{a.rationale}</div>
                  )}
                </div>
                <button
                  className="text-xs text-muted-foreground hover:text-destructive"
                  onClick={() => remove(a.id)}
                  aria-label="削除"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="アクションを追加…"
            onKeyDown={(e) => {
              if (e.key === 'Enter') add();
            }}
          />
          <Button size="md" onClick={add} disabled={!draft.trim() || saveMut.isPending}>
            追加
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PagePerformanceBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'page-performance', days],
    queryFn: () => fetchPagePerformance(days, 20),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="記事/ページ別パフォーマンス TOP 20"
          help="page_performance"
          ds={['ga4_page', 'gsc_page', 'citation', 'contents']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            GSC / GA4 のページ単位データがまだありません(初回ジョブ後に表示されます)。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">ページ</th>
                  <th className="py-1 text-right">セッション</th>
                  <th className="py-1 text-right">CL</th>
                  <th className="py-1 text-right">表示</th>
                  <th className="py-1 text-right">CTR</th>
                  <th className="py-1 text-right">順位</th>
                  <th className="py-1 text-right">AI 引用</th>
                </tr>
              </thead>
              <tbody>
                {data.map((p) => {
                  const ctrAlert =
                    p.ctr !== null && p.avg_position !== null && p.avg_position <= 3 && p.ctr < 0.05;
                  const ctrOpportunity =
                    p.ctr !== null && p.avg_position !== null && p.avg_position > 10 && p.ctr > 0.05;
                  return (
                    <tr key={p.page_path} className="border-t border-border">
                      <td className="py-1 max-w-[20rem] truncate">
                        <span className="font-medium">{p.title || p.page_path}</span>
                        <div className="text-[10px] text-muted-foreground truncate">
                          {p.page_path}
                        </div>
                      </td>
                      <td className="py-1 text-right tabular-nums">{p.sessions}</td>
                      <td className="py-1 text-right tabular-nums">{p.clicks}</td>
                      <td className="py-1 text-right tabular-nums">{p.impressions}</td>
                      <td
                        className="py-1 text-right tabular-nums font-medium"
                        title={
                          ctrAlert
                            ? '上位表示なのに CTR が低い: タイトル/ディスクリプション要改善'
                            : ctrOpportunity
                              ? '低順位なのに CTR 良好: 順位を上げる伸びしろあり'
                              : undefined
                        }
                      >
                        {p.ctr === null ? (
                          '—'
                        ) : (
                          <span
                            className={
                              ctrAlert
                                ? 'text-rose-600 dark:text-rose-400'
                                : ctrOpportunity
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : ''
                            }
                          >
                            {(p.ctr * 100).toFixed(1)}%
                          </span>
                        )}
                      </td>
                      <td className="py-1 text-right tabular-nums">
                        {p.avg_position === null ? '—' : p.avg_position.toFixed(1)}
                      </td>
                      <td className="py-1 text-right tabular-nums">{p.citation_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FunnelBlock({ days }: { days: number }) {
  // 漏斗は短期間だと数字が出にくいので、最低 30 日は確保
  const effective = Math.max(days, 30);
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'funnel', effective],
    queryFn: () => fetchFunnel(effective),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="コンバージョン漏斗"
          help="funnel"
          ds={['inquiries']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">データがありません。</p>
        ) : (
          <div className="space-y-3">
            {data.stages.map((s) => {
              const max = data.stages[0]?.count || 1;
              const pct = (s.count / max) * 100;
              return (
                <div key={s.status}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{s.status}</span>
                    <span className="tabular-nums">
                      <b>{s.count}</b>
                      {s.amount_yen > 0 && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          ¥{s.amount_yen.toLocaleString()}
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
            <div className="grid grid-cols-2 gap-3 pt-2 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">CV 率(受注 / 新規)</div>
                <div className="text-lg font-semibold tabular-nums">
                  {data.cv_rate === null ? '—' : `${(data.cv_rate * 100).toFixed(1)}%`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">平均受注単価</div>
                <div className="text-lg font-semibold tabular-nums">
                  {data.avg_amount_yen === null
                    ? '—'
                    : `¥${data.avg_amount_yen.toLocaleString()}`}
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const ACTION_LABEL: Record<string, string> = {
  win: '勝ち取る',
  optimize: '最適化',
  create: '新規記事',
  monitor: '観察',
};
const ACTION_BG: Record<string, string> = {
  win: 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300',
  optimize: 'bg-amber-500/20 text-amber-700 dark:text-amber-300',
  create: 'bg-sky-500/20 text-sky-700 dark:text-sky-300',
  monitor: 'bg-muted text-muted-foreground',
};

function QueryRankChangesBlock() {
  // 順位変動は短期(14 日 vs その前の 14 日)で見るのが筋なので、画面の期間セレクタに依存しない
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'query-rank-changes', 14],
    queryFn: () => fetchQueryRankChanges(14, 10),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="クエリ順位変動 Top 10(直近 14 日 vs その前 14 日)"
          help="query_rank_changes"
          ds={['gsc_query']}
        />
        <p className="mt-1 text-[11px] text-muted-foreground">
          直近期間に 50 表示以上のクエリのみ。Δ は前期間の平均順位 − 直近の平均順位。
          プラス=順位上昇、マイナス=順位下落。
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : !data || (data.rising.length === 0 && data.falling.length === 0) ? (
          <p className="text-sm text-muted-foreground">
            集計に必要な GSC データがまだ揃っていません。
          </p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                ▲ 上昇クエリ
              </h3>
              {data.rising.length === 0 ? (
                <p className="text-xs text-muted-foreground">該当なし</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="py-1">クエリ</th>
                      <th className="py-1 text-right">前期</th>
                      <th className="py-1 text-right">直近</th>
                      <th className="py-1 text-right">Δ</th>
                      <th className="py-1 text-right">表示</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rising.map((r, i) => (
                      <tr key={i} className="border-t border-border">
                        <td className="py-1 max-w-[14rem] truncate">{r.query_text}</td>
                        <td className="py-1 text-right tabular-nums text-muted-foreground">
                          {r.avg_position_prev?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums">
                          {r.avg_position_recent?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums font-medium text-emerald-600 dark:text-emerald-400">
                          +{r.delta?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums">
                          {r.impressions_recent}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold text-rose-600 dark:text-rose-400">
                ▼ 下落クエリ
              </h3>
              {data.falling.length === 0 ? (
                <p className="text-xs text-muted-foreground">該当なし</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="py-1">クエリ</th>
                      <th className="py-1 text-right">前期</th>
                      <th className="py-1 text-right">直近</th>
                      <th className="py-1 text-right">Δ</th>
                      <th className="py-1 text-right">表示</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.falling.map((r, i) => (
                      <tr key={i} className="border-t border-border">
                        <td className="py-1 max-w-[14rem] truncate">{r.query_text}</td>
                        <td className="py-1 text-right tabular-nums text-muted-foreground">
                          {r.avg_position_prev?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums">
                          {r.avg_position_recent?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums font-medium text-rose-600 dark:text-rose-400">
                          {r.delta?.toFixed(1) ?? '—'}
                        </td>
                        <td className="py-1 text-right tabular-nums">
                          {r.impressions_recent}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function KeywordOpportunityBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'keyword-opportunity', days],
    queryFn: () => fetchKeywordOpportunity(days, 30),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="キーワード機会マトリクス"
          help="keyword_opportunity"
          ds={['gsc_query', 'citation']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">GSC データがまだありません。</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">クエリ</th>
                  <th className="py-1 text-right">表示</th>
                  <th className="py-1 text-right">順位</th>
                  <th className="py-1 text-right">引用率</th>
                  <th className="py-1">推奨</th>
                </tr>
              </thead>
              <tbody>
                {data.map((q, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1 max-w-[18rem] truncate">{q.query_text}</td>
                    <td className="py-1 text-right tabular-nums">{q.impressions}</td>
                    <td className="py-1 text-right tabular-nums">
                      {q.avg_position === null ? '—' : q.avg_position.toFixed(1)}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {(q.citation_rate * 100).toFixed(0)}%
                    </td>
                    <td className="py-1">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-[10px] ${ACTION_BG[q.recommended_action]}`}
                      >
                        {ACTION_LABEL[q.recommended_action]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CompetitorContentBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'competitor-content', days],
    queryFn: () => fetchCompetitorContent(days, 20),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="競合に引用された記事 TOP 20"
          help="competitor_content"
          ds={['citation', 'competitor_post']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            自社以外の URL が AI に引用された記録がまだありません。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((c, i) => (
              <li key={i} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
                <div className="flex items-baseline justify-between gap-2">
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-primary hover:underline truncate"
                  >
                    {c.url}
                  </a>
                  <span className="text-xs tabular-nums">{c.cite_count}回</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  ドメイン: {c.domain}
                  {c.sample_query && <span className="ml-3">きっかけ: 「{c.sample_query}」</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

const METRIC_LABEL: Record<AlertRule['metric'], string> = {
  sessions_drop_pct: 'セッションが先週比 X% 以上下落',
  citations_drop_pct: 'AI 引用回数が先週比 X% 以上下落',
  inquiries_zero_days: '直近 N 日間の問い合わせがゼロ',
  anomaly: '異常値検出(7日移動平均から ±2σ)',
};

function AlertRulesEditor() {
  const qc = useQueryClient();
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'alert-rules'],
    queryFn: fetchAlertRules,
  });
  const [editing, setEditing] = useState<AlertRule[]>([]);
  useEffect(() => {
    if (!isPending) setEditing(data);
  }, [isPending, data]);

  const saveMut = useMutation({
    mutationFn: (items: AlertRule[]) => replaceAlertRules(items),
    onSuccess: (data) => {
      qc.setQueryData(['dashboard', 'alert-rules'], data);
      setEditing(data);
    },
  });

  const update = (idx: number, patch: Partial<AlertRule>) => {
    const next = [...editing];
    next[idx] = { ...next[idx], ...patch };
    setEditing(next);
  };
  const remove = (idx: number) => {
    setEditing(editing.filter((_, i) => i !== idx));
  };
  const add = () => {
    setEditing([
      ...editing,
      {
        id: crypto.randomUUID(),
        metric: 'sessions_drop_pct',
        threshold: 20,
        notify_email: null,
        notify_slack_webhook: null,
        enabled: true,
      },
    ]);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <HeaderRow title="アラート設定" help="alerts" />
          <Button size="sm" onClick={() => saveMut.mutate(editing)} disabled={saveMut.isPending}>
            {saveMut.isPending ? '保存中…' : '保存'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {editing.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            まだルールがありません。「追加」を押してしきい値を設定してください。
          </p>
        ) : (
          editing.map((r, idx) => (
            <div key={r.id} className="rounded border border-border p-3 space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={r.enabled}
                  onChange={(e) => update(idx, { enabled: e.target.checked })}
                />
                <select
                  value={r.metric}
                  onChange={(e) => update(idx, { metric: e.target.value as AlertRule['metric'] })}
                  className="h-9 flex-1 rounded-md border border-input bg-background px-2 text-sm"
                >
                  {Object.entries(METRIC_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <button
                  className="text-xs text-muted-foreground hover:text-destructive"
                  onClick={() => remove(idx)}
                  aria-label="削除"
                >
                  ✕
                </button>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Input
                  type="number"
                  value={r.threshold}
                  onChange={(e) => update(idx, { threshold: Number(e.target.value) })}
                  placeholder="しきい値"
                />
                <Input
                  type="email"
                  value={r.notify_email ?? ''}
                  onChange={(e) => update(idx, { notify_email: e.target.value || null })}
                  placeholder="通知メール (任意)"
                />
                <Input
                  type="url"
                  value={r.notify_slack_webhook ?? ''}
                  onChange={(e) =>
                    update(idx, { notify_slack_webhook: e.target.value || null })
                  }
                  placeholder="Slack Webhook URL (任意)"
                />
              </div>
            </div>
          ))
        )}
        <Button size="sm" variant="secondary" onClick={add}>
          + ルール追加
        </Button>
        <p className="text-xs text-muted-foreground">
          毎週月曜 6:30 JST に評価し、しきい値を超えたら登録した連絡先に通知します。
        </p>
      </CardContent>
    </Card>
  );
}

function ReportsBlock() {
  const qc = useQueryClient();
  const { data = [], isPending } = useQuery({
    queryKey: ['reports'],
    queryFn: fetchReports,
  });
  const shareMut = useMutation({
    mutationFn: (id: string) => createShareToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  });
  const revokeMut = useMutation({
    mutationFn: (id: string) => revokeShareToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow title="月次/週次レポート" help="reports" />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            レポートはまだ生成されていません(毎月 3 日 7:00 JST に自動生成されます)。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((r) => {
              const sharedUrl = r.share_token
                ? `${window.location.origin}/marketer/public/reports/${r.share_token}`
                : null;
              return (
                <li
                  key={r.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-border p-2"
                >
                  <div>
                    <div className="text-sm font-medium">
                      {r.report_type === 'monthly' ? '月次' : '週次'} {r.period}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(r.generated_at).toLocaleString('ja-JP')}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={reportPdfUrl(r.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      PDF
                    </a>
                    {r.share_token ? (
                      <>
                        <a
                          href={sharedUrl ?? '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline"
                          title={sharedUrl ?? ''}
                        >
                          公開 URL
                        </a>
                        <button
                          className="text-xs text-muted-foreground hover:text-destructive"
                          onClick={() => revokeMut.mutate(r.id)}
                        >
                          公開停止
                        </button>
                      </>
                    ) : (
                      <button
                        className="text-xs text-primary hover:underline"
                        onClick={() => shareMut.mutate(r.id)}
                      >
                        公開 URL を発行
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function CvPathsBlock({ days }: { days: number }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'cv-paths', days],
    queryFn: () => fetchCvPaths(Math.max(days, 30)),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="流入チャネル別 CV(按分概算)"
          help="cv_paths"
          ds={['ga4_daily', 'ga4_ai_referral', 'inquiries']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">データがありません。</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">チャネル</th>
                <th className="py-1 text-right">セッション</th>
                <th className="py-1 text-right">CV</th>
                <th className="py-1 text-right">CV 率</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.channel} className="border-t border-border">
                  <td className="py-1">{c.channel}</td>
                  <td className="py-1 text-right tabular-nums">{c.sessions}</td>
                  <td className="py-1 text-right tabular-nums">{c.inquiries}</td>
                  <td className="py-1 text-right tabular-nums">
                    {c.cv_rate === null ? '—' : `${(c.cv_rate * 100).toFixed(2)}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-2 text-[10px] text-muted-foreground">
          ※ inquiry の正確な参照元が記録されていないため、セッション割合で按分した概算値です。
        </p>
      </CardContent>
    </Card>
  );
}

function PageRankDecayBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'page-rank-decay'],
    queryFn: () => fetchPageRankDecay(20),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="順位下落ページ TOP 20(直近 14 日 vs その前 30 日)"
          help="page_rank_decay"
          ds={['gsc_page']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            順位下落しているページは検出されていません(GSC データが揃ったら表示されます)。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">ページ</th>
                  <th className="py-1 text-right">直近順位</th>
                  <th className="py-1 text-right">基準順位</th>
                  <th className="py-1 text-right">下落幅</th>
                  <th className="py-1 text-right">直近表示</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.page} className="border-t border-border">
                    <td className="py-1 max-w-[18rem] truncate">
                      <span className="font-medium">{r.title || r.page}</span>
                      <div className="text-[10px] text-muted-foreground truncate">{r.page}</div>
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {r.avg_position_recent?.toFixed(1) ?? '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {r.avg_position_baseline?.toFixed(1) ?? '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums text-rose-600 dark:text-rose-400">
                      {r.delta !== null ? `+${r.delta.toFixed(1)}` : '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">{r.impressions_recent}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BrandSearchBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'brand-search'],
    queryFn: () => fetchBrandSearch(12),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="ブランド検索ボリューム(月次・直近 12 ヶ月)"
          help="brand_search"
          ds={['gsc_query']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            ブランド名(社名・ドメイン)を含むクエリの GSC データがまだありません。
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="period" stroke="hsl(var(--muted-foreground))" fontSize={10} />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  color: 'hsl(var(--card-foreground))',
                }}
              />
              <Line
                type="monotone"
                dataKey="impressions"
                name="表示"
                stroke="hsl(var(--primary))"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="clicks"
                name="クリック"
                stroke="hsl(var(--destructive))"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

const INTENT_LABEL: Record<string, string> = {
  transactional: '取引型(おすすめ・比較・依頼)',
  navigational: 'ナビ型(やり方・始め方)',
  informational: '情報収集型(とは・事例)',
  other: 'その他',
};

function SearchIntentBlock({ days }: { days: number }) {
  const effective = Math.max(days, 30);
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'search-intent', effective],
    queryFn: () => fetchSearchIntent(effective),
  });
  const totalImp = data.reduce((s, d) => s + d.impressions, 0);
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="検索意図の分布"
          help="search_intent"
          ds={['gsc_query']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">GSC データがまだありません。</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">意図</th>
                <th className="py-1 text-right">表示</th>
                <th className="py-1 text-right">CL</th>
                <th className="py-1 text-right">クエリ数</th>
                <th className="py-1 text-right">平均順位</th>
                <th className="py-1 text-right">構成比</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.intent} className="border-t border-border">
                  <td className="py-1">{INTENT_LABEL[r.intent] ?? r.intent}</td>
                  <td className="py-1 text-right tabular-nums">{r.impressions}</td>
                  <td className="py-1 text-right tabular-nums">{r.clicks}</td>
                  <td className="py-1 text-right tabular-nums">{r.queries}</td>
                  <td className="py-1 text-right tabular-nums">
                    {r.avg_position?.toFixed(1) ?? '—'}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {totalImp > 0 ? `${((r.impressions / totalImp) * 100).toFixed(0)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

const WEEKDAY_JP = ['月', '火', '水', '木', '金', '土', '日'];

function HourWeekdayHeatmapBlock({ days }: { days: number }) {
  // 曜日 × 時間帯は短期間だとサンプルが偏るので、最低 14 日は確保
  const effective = Math.max(days, 14);
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'hour-weekday-heatmap', effective],
    queryFn: () => fetchHourWeekdayHeatmap(effective),
  });
  const grid: Record<string, number> = {};
  let max = 0;
  for (const c of data?.cells ?? []) {
    grid[`${c.weekday}-${c.hour}`] = c.sessions;
    if (c.sessions > max) max = c.sessions;
  }
  // 大きな値と小さな値の差が極端なときでも小さい値が見えるよう、log スケールで濃さを決める。
  // ratio = log(1+v) / log(1+max) なら 1 セッションでも約 1/log(1+max) の濃さで残る。
  const logMax = Math.log1p(max);
  const peakLabel = (c: { weekday: number; hour: number; sessions: number }) =>
    `${WEEKDAY_JP[c.weekday]} ${c.hour}:00台 — ${c.sessions} セッション`;
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="曜日 × 時間帯ヒートマップ(合計セッション)"
          help="hour_weekday"
          ds={['ga4_hourly']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : !data || data.cells.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            GA4 hourly データがまだありません(次回 GA4 ジョブで蓄積開始)。
          </p>
        ) : (
          <div className="space-y-2">
            <table className="w-full table-fixed text-[10px]">
              <colgroup>
                {/* 曜日ラベル列(左端、固定幅) */}
                <col className="w-8" />
                {/* 24 時間ぶんの均等配分 */}
                {Array.from({ length: 24 }, (_, h) => (
                  <col key={h} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th className="py-1 pr-1 text-left text-muted-foreground">曜日＼時</th>
                  {Array.from({ length: 24 }, (_, h) => (
                    <th key={h} className="px-0 py-1 text-center text-muted-foreground">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {WEEKDAY_JP.map((wd, w) => (
                  <tr key={w}>
                    <td className="py-0.5 pr-1 text-muted-foreground">{wd}</td>
                    {Array.from({ length: 24 }, (_, h) => {
                      const v = grid[`${w}-${h}`] ?? 0;
                      const ratio = logMax > 0 && v > 0 ? Math.log1p(v) / logMax : 0;
                      const bg =
                        v > 0
                          ? `rgba(16, 185, 129, ${0.12 + ratio * 0.78})`
                          : 'transparent';
                      return (
                        <td key={h} className="p-0">
                          <div
                            className="mx-px h-6 rounded text-center leading-6 tabular-nums"
                            style={{ backgroundColor: bg }}
                            title={
                              v > 0
                                ? `${wd} ${h}:00 台 — ${v} セッション`
                                : 'アクセスなし'
                            }
                          >
                            {v > 0 ? v : ''}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {data.peaks.length > 0 && (
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">ピーク時間帯:</span>{' '}
                {data.peaks.map(peakLabel).join(' / ')}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SeasonalityBlock({ days }: { days: number }) {
  // 季節性は月単位の集計なので、画面の days を月数に変換(最低 6 ヶ月)
  const months = Math.max(6, Math.ceil(days / 30));
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'seasonality', months],
    queryFn: () => fetchSeasonality(months),
  });
  // 12 month × 7 weekday マトリクスに展開
  const grid: Record<string, number> = {};
  let max = 0;
  for (const c of data) {
    const k = `${c.month}-${c.weekday}`;
    grid[k] = c.avg_sessions;
    if (c.avg_sessions > max) max = c.avg_sessions;
  }
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="季節性ヒートマップ(曜日 × 月平均セッション)"
          help="seasonality"
          ds={['ga4_daily']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">データがまだ蓄積されていません。</p>
        ) : (
          <table className="w-full table-fixed text-xs">
            <colgroup>
              {/* 曜日ラベル列(左端、固定幅) */}
              <col className="w-10" />
              {/* 12 ヶ月ぶんの均等配分 */}
              {Array.from({ length: 12 }, (_, i) => (
                <col key={i} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th className="py-1 pr-1 text-left text-muted-foreground">曜日＼月</th>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <th key={m} className="px-0 py-1 text-center text-muted-foreground">
                    {m}月
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {WEEKDAY_JP.map((wd, w) => (
                <tr key={w}>
                  <td className="py-0.5 pr-1 text-muted-foreground">{wd}</td>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                    const v = grid[`${m}-${w}`];
                    const ratio = max > 0 && v ? v / max : 0;
                    const bg = v
                      ? `rgba(99, 102, 241, ${0.1 + ratio * 0.7})`
                      : 'transparent';
                    return (
                      <td key={m} className="p-0">
                        <div
                          className="mx-px rounded px-1 py-1 text-center tabular-nums"
                          style={{ backgroundColor: bg }}
                          title={v ? `${m}月 ${wd}: ${v} セッション/日` : 'データなし'}
                        >
                          {v ? Math.round(v) : '—'}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

const AREA_LABEL: Record<string, string> = {
  local_district_hq: '本拠地(平野区)',
  local_radius: '半径10km圏',
  geo_intent: '距離意図',
  industry_local: '地域×業種',
  competitive: '競合比較',
};

function AreaPerformanceBlock({ days }: { days: number }) {
  const effective = Math.max(days, 30);
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'area-performance', effective],
    queryFn: () => fetchAreaPerformance(effective),
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="エリア別パフォーマンス"
          help="area_performance"
          ds={['gsc_query', 'citation']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            ターゲットクエリの GSC データがまだ十分にありません。
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1">クラスタ</th>
                <th className="py-1 text-right">表示</th>
                <th className="py-1 text-right">CL</th>
                <th className="py-1 text-right">平均順位</th>
                <th className="py-1 text-right">引用率</th>
                <th className="py-1 text-right">クエリ数</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.cluster_id} className="border-t border-border">
                  <td className="py-1">{AREA_LABEL[r.cluster_id] ?? r.cluster_id}</td>
                  <td className="py-1 text-right tabular-nums">{r.impressions}</td>
                  <td className="py-1 text-right tabular-nums">{r.clicks}</td>
                  <td className="py-1 text-right tabular-nums">
                    {r.avg_position?.toFixed(1) ?? '—'}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {(r.citation_rate * 100).toFixed(0)}%
                  </td>
                  <td className="py-1 text-right tabular-nums">{r.queries}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function _scoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground';
  if (score >= 90) return 'text-emerald-600 dark:text-emerald-400';
  if (score >= 50) return 'text-amber-600 dark:text-amber-400';
  return 'text-rose-600 dark:text-rose-400';
}

function PageSpeedBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'page-speed'],
    queryFn: fetchPageSpeed,
  });
  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="Core Web Vitals(直近計測)"
          help="page_speed"
          ds={['page_speed']}
        />
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            まだ計測がありません。週次ジョブ(月曜 5:30 JST)または環境変数
            <code className="mx-1">MARKETER_PAGESPEED_API_KEY</code>
            設定後の手動キックを待ってください。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1">URL / strategy</th>
                  <th className="py-1 text-right">スコア</th>
                  <th className="py-1 text-right">LCP</th>
                  <th className="py-1 text-right">CLS</th>
                  <th className="py-1 text-right">INP</th>
                  <th className="py-1 text-right">計測日</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1 max-w-[20rem] truncate">
                      {r.page_url}
                      <span className="ml-2 text-[10px] text-muted-foreground">
                        ({r.strategy})
                      </span>
                    </td>
                    <td
                      className={`py-1 text-right tabular-nums ${_scoreColor(r.performance_score)}`}
                    >
                      {r.performance_score ?? '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {r.lcp_ms ? `${(r.lcp_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {r.cls !== null ? r.cls.toFixed(3) : '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">
                      {r.inp_ms !== null ? `${r.inp_ms}ms` : '—'}
                    </td>
                    <td className="py-1 text-right tabular-nums">{r.measured_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MarketingActionRow({ a }: { a: MarketingAction }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(a.action_date);
  const [category, setCategory] = useState<MarketingActionCategory>(a.category);
  const [title, setTitle] = useState(a.title);
  const [description, setDescription] = useState(a.description ?? '');

  const updateMut = useMutation({
    mutationFn: () =>
      updateMarketingAction(a.id, {
        action_date: date,
        category,
        title,
        description: description || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['marketing-actions'] });
      setEditing(false);
    },
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteMarketingAction(a.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['marketing-actions'] }),
  });

  if (editing) {
    return (
      <li className="rounded border border-primary/40 bg-primary/5 p-2 text-sm space-y-2">
        <div className="grid gap-2 md:grid-cols-[120px_140px_1fr]">
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="実施日"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as MarketingActionCategory)}
            className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            aria-label="カテゴリ"
          >
            {(Object.entries(CATEGORY_LABEL) as [MarketingActionCategory, string][]).map(
              ([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ),
            )}
          </select>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="施策タイトル"
          />
        </div>
        <Input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="補足(任意)"
        />
        <div className="flex items-center justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDate(a.action_date);
              setCategory(a.category);
              setTitle(a.title);
              setDescription(a.description ?? '');
              setEditing(false);
            }}
            disabled={updateMut.isPending}
          >
            キャンセル
          </Button>
          <Button
            size="sm"
            onClick={() => updateMut.mutate()}
            disabled={!title.trim() || updateMut.isPending}
          >
            {updateMut.isPending ? '保存中…' : '保存'}
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li className="flex items-start gap-3 rounded border border-border p-2 text-sm">
      <div className="text-xs tabular-nums text-muted-foreground" style={{ minWidth: 90 }}>
        {a.action_date}
      </div>
      <span
        className="rounded px-2 py-0.5 text-[10px] font-medium"
        style={{
          backgroundColor: `${CATEGORY_COLOR[a.category]}26`, // 15% alpha
          color: CATEGORY_COLOR[a.category],
        }}
      >
        {CATEGORY_LABEL[a.category]}
      </span>
      <div className="flex-1">
        <div className="font-medium">{a.title}</div>
        {a.description && (
          <div className="text-xs text-muted-foreground">{a.description}</div>
        )}
      </div>
      <button
        className="text-xs text-muted-foreground hover:text-primary"
        onClick={() => setEditing(true)}
        aria-label="編集"
      >
        編集
      </button>
      <button
        className="text-xs text-muted-foreground hover:text-destructive"
        onClick={() => {
          if (confirm(`「${a.title}」を削除しますか？`)) deleteMut.mutate();
        }}
        aria-label="削除"
        disabled={deleteMut.isPending}
      >
        ✕
      </button>
    </li>
  );
}

function MarketingActionsBlock() {
  const qc = useQueryClient();
  const { data = [], isPending } = useQuery({
    queryKey: ['marketing-actions', 'all'],
    queryFn: () => fetchMarketingActions(),
  });
  const [actionDate, setActionDate] = useState<string>(
    new Date().toISOString().slice(0, 10),
  );
  const [category, setCategory] = useState<MarketingActionCategory>('content_publish');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const createMut = useMutation({
    mutationFn: () =>
      createMarketingAction({
        action_date: actionDate,
        category,
        title,
        description: description || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['marketing-actions'] });
      setTitle('');
      setDescription('');
    },
  });

  return (
    <Card>
      <CardHeader>
        <HeaderRow
          title="施策タイムライン"
          help="marketing_actions"
          ds={['marketing_actions']}
        />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 md:grid-cols-[120px_140px_1fr_auto]">
          <Input
            type="date"
            value={actionDate}
            onChange={(e) => setActionDate(e.target.value)}
            aria-label="実施日"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as MarketingActionCategory)}
            className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            aria-label="カテゴリ"
          >
            {(Object.entries(CATEGORY_LABEL) as [MarketingActionCategory, string][]).map(
              ([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ),
            )}
          </select>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="施策タイトル(例: TOP ページのリライト)"
          />
          <Button
            size="md"
            onClick={() => createMut.mutate()}
            disabled={!title.trim() || createMut.isPending}
          >
            追加
          </Button>
        </div>
        <Input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="補足(任意): 何をしたか、狙い、期待効果など"
        />
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            まだ施策が登録されていません。上のフォームから追加してください。
          </p>
        ) : (
          <ul className="space-y-2">
            {data.map((a) => (
              <MarketingActionRow key={a.id} a={a} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

const FOUNDED_DATE = '2022-08-19'; // kiseeeen 創業日(全期間表示の起点)

const PERIOD_OPTIONS = [
  { value: '7', label: '過去 7 日' },
  { value: '30', label: '過去 30 日' },
  { value: '90', label: '過去 90 日' },
  { value: '180', label: '過去 180 日' },
  { value: '365', label: '過去 365 日' },
  { value: 'all', label: '全期間(2022-08-19〜)' },
];

function _daysFromPeriod(period: string): number {
  if (period === 'all') {
    const start = new Date(FOUNDED_DATE);
    return Math.max(1, Math.floor((Date.now() - start.getTime()) / (1000 * 60 * 60 * 24)));
  }
  return Number(period) || 30;
}

export default function DashboardPage() {
  const [period, setPeriod] = useState<string>('30');
  const days = _daysFromPeriod(period);
  const isAll = period === 'all';

  const { data, isPending, error } = useQuery<KpiSummary, Error>({
    queryKey: ['kpi', 'summary', period],
    queryFn: () =>
      fetchKpiSummary(isAll ? { startDate: FOUNDED_DATE } : { days }),
  });

  // 施策(マーケティングアクション)— 全期間の目印として常に取得
  const { data: actions = [] } = useQuery({
    queryKey: ['marketing-actions', 'all'],
    queryFn: () => fetchMarketingActions(),
  });

  const periodHint = data ? `過去 ${data.period_days} 日` : `過去 ${days} 日`;

  // 施策をグラフに重ねるため、各日付(または週/月の bucket 開始日)に紐付ける
  const actionsByBucket = (() => {
    const map = new Map<string, MarketingAction[]>();
    if (!data) return map;
    const granularity = data.granularity;
    for (const a of actions) {
      const d = new Date(a.action_date);
      let bucket = a.action_date;
      if (granularity === 'week') {
        const day = d.getDay() || 7; // Sun=0 -> 7
        const monday = new Date(d);
        monday.setDate(d.getDate() - (day - 1));
        bucket = monday.toISOString().slice(0, 10);
      } else if (granularity === 'month') {
        bucket = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
      }
      const arr = map.get(bucket) ?? [];
      arr.push(a);
      map.set(bucket, arr);
    }
    return map;
  })();
  const seriesWithActions = (data?.series ?? []).map((p) => ({
    ...p,
    actions: actionsByBucket.get(p.date) ?? [],
    actions_count: (actionsByBucket.get(p.date) ?? []).length,
  }));

  const overview = (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="AI 引用回数"
          metric={data?.metrics?.ai_citation_count}
          hint={periodHint}
          coverageSince={data?.coverage?.citations_since}
          helpKey="kpi_citation"
        />
        <KpiCard
          label="オーガニックセッション"
          metric={data?.metrics?.sessions}
          hint={periodHint}
          coverageSince={data?.coverage?.sessions_since}
          helpKey="kpi_sessions"
        />
        <KpiCard
          label="問い合わせ数"
          metric={data?.metrics?.inquiries_count}
          hint={periodHint}
          coverageSince={data?.coverage?.inquiries_since}
          helpKey="kpi_inquiries"
        />
        <KpiCard
          label="リード CVR"
          rate={
            data?.rate_metrics?.lead_cvr
              ? {
                  value: data.rate_metrics.lead_cvr.value,
                  delta_pct: data.rate_metrics.lead_cvr.delta_pct,
                  yoy_pct: data.rate_metrics.lead_cvr.yoy_pct,
                }
              : undefined
          }
          rateHint={`問い合わせ ÷ セッション(${periodHint})`}
          coverageSince={data?.coverage?.inquiries_since}
          helpKey="kpi_cvr"
        />
        <KpiCard
          label="公開記事数"
          metric={data?.metrics?.contents_published}
          hint={periodHint}
          coverageSince={data?.coverage?.contents_since}
          helpKey="kpi_contents"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <ObjectivesBlock />
        </div>
        <ObjectivesEditor />
      </div>

      <Card>
        <CardHeader>
          <HeaderRow
            title="セッション・引用推移(7 日移動平均 + 異常値ハイライト)"
            help="trend"
            ds={['ga4_daily', 'citation', 'inquiries', 'marketing_actions']}
          />
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
            <span className="font-medium">施策の色:</span>
            {(Object.keys(CATEGORY_LABEL) as MarketingActionCategory[]).map((k) => (
              <span key={k} className="inline-flex items-center gap-1">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLOR[k] }}
                />
                {CATEGORY_LABEL[k]}
              </span>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <p className="text-sm text-muted-foreground">読み込み中…</p>
          ) : error ? (
            <p className="text-sm text-destructive">取得に失敗しました</p>
          ) : !data || data.series.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              データがまだ蓄積されていません(GSC/GA4/引用モニタの初回ジョブを待ってください)
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={seriesWithActions}
                margin={{ top: 5, right: 16, bottom: 24, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  stroke="hsl(var(--muted-foreground))"
                  tick={DateTick}
                  height={56}
                  interval="preserveStartEnd"
                  minTickGap={12}
                />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip content={<TrendTooltip />} />
                <Line
                  type="monotone"
                  dataKey="sessions"
                  name="sessions"
                  stroke="hsl(var(--primary))"
                  dot={(props: {
                    cx?: number;
                    cy?: number;
                    payload?: { is_anomaly?: boolean };
                    index?: number;
                  }) => {
                    const { cx, cy, payload, index } = props;
                    if (cx === undefined || cy === undefined) {
                      return <g key={`dot-empty-${index ?? ''}`} />;
                    }
                    return payload?.is_anomaly ? (
                      <circle
                        key={`dot-${index ?? ''}`}
                        cx={cx}
                        cy={cy}
                        r={5}
                        fill="hsl(var(--destructive))"
                        stroke="white"
                        strokeWidth={1}
                      />
                    ) : (
                      <g key={`dot-${index ?? ''}`} />
                    );
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="sessions_ma7"
                  name="7日移動平均"
                  stroke="hsl(var(--primary))"
                  strokeDasharray="4 4"
                  strokeOpacity={0.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="ai_citation_count"
                  name="AI 引用"
                  stroke="hsl(var(--destructive))"
                  dot={false}
                />
                {/* 施策マーカー: セッション線の上に丸を載せる。色はカテゴリ準拠。
                    同日複数カテゴリの場合は最初の施策の色を採用(全件はツールチップに出る)。 */}
                <Line
                  type="monotone"
                  dataKey="sessions"
                  name="施策"
                  stroke="transparent"
                  legendType="none"
                  isAnimationActive={false}
                  activeDot={false}
                  dot={(props: {
                    cx?: number;
                    cy?: number;
                    payload?: {
                      actions_count?: number;
                      actions?: { category: MarketingActionCategory }[];
                    };
                    index?: number;
                  }) => {
                    const { cx, cy, payload, index } = props;
                    if (cx === undefined || cy === undefined || !payload?.actions_count) {
                      return <g key={`act-empty-${index ?? ''}`} />;
                    }
                    const cat = payload.actions?.[0]?.category ?? 'other';
                    return (
                      <circle
                        key={`act-${index ?? ''}`}
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={CATEGORY_COLOR[cat]}
                        stroke="white"
                        strokeWidth={1.5}
                      />
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ChannelBlock days={days} />
        <ChannelCvrBlock days={days} />
        <AiReferralsBlock days={days} />
        <ClusterCitationBlock days={days} />
      </div>

      <ReferrersBlock days={days} />
      <CvPathsBlock days={days} />
      <BrandSearchBlock />
      <HourWeekdayHeatmapBlock days={days} />
      <SeasonalityBlock days={days} />

      <NextActionsBlock />
    </div>
  );

  const contentTab = (
    <div className="space-y-6">
      <PagePerformanceBlock days={days} />
      <PageRankDecayBlock />
      <PageSpeedBlock />
      <FunnelBlock days={days} />
    </div>
  );

  const keywordTab = (
    <div className="space-y-6">
      <QueryRankChangesBlock />
      <HeatmapBlock days={days} />
      <SearchIntentBlock days={days} />
      <AreaPerformanceBlock days={days} />
      <KeywordOpportunityBlock days={days} />
      <TopQueriesBlock days={days} />
    </div>
  );

  const competitorTab = (
    <div className="space-y-6">
      <CompetitorTopBlock days={days} />
      <CompetitorContentBlock days={days} />
    </div>
  );

  const settingsTab = (
    <div className="space-y-6">
      <AlertRulesEditor />
      <ReportsBlock />
    </div>
  );

  const actionsTab = (
    <div className="space-y-6">
      <MarketingActionsBlock />
    </div>
  );

  return (
    <div className="space-y-6">
      <AnomalyBanner />
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">ダッシュボード</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">期間</span>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            aria-label="期間"
          >
            {PERIOD_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Tabs
        defaultId="overview"
        tabs={[
          { id: 'overview', label: '概要', content: overview },
          { id: 'content', label: 'コンテンツ分析', content: contentTab },
          { id: 'keyword', label: 'キーワード戦略', content: keywordTab },
          { id: 'competitor', label: '競合', content: competitorTab },
          { id: 'actions', label: '施策', content: actionsTab },
          { id: 'settings', label: 'アラート/レポート', content: settingsTab },
        ]}
      />
    </div>
  );
}
