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
  fetchChannelBreakdown,
  fetchClusterCitation,
  fetchCompetitorContent,
  fetchCompetitorPatternsTop,
  fetchFunnel,
  fetchHeatmap,
  fetchKeywordOpportunity,
  fetchNextActions,
  fetchObjectives,
  fetchPagePerformance,
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
  createShareToken,
  fetchReports,
  reportPdfUrl,
  revokeShareToken,
} from '@/api/reports';
import { fetchAnomalies, type Anomaly } from '@/api/strategic';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
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
}: {
  label: string;
  metric?: KpiMetric;
  hint?: string;
  coverageSince?: string | null;
}) {
  // YoY を出すには 1 年以上の蓄積が必要
  const hasYearOfData = coverageSince
    ? Date.now() - new Date(coverageSince).getTime() >= 365 * 24 * 3600 * 1000
    : false;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tabular-nums">{metric?.value ?? '—'}</div>
        <div className="mt-1 flex flex-col gap-0.5">
          {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <DeltaBadge delta={metric?.delta_pct ?? null} label="前期間比" />
            {hasYearOfData ? (
              <DeltaBadge delta={metric?.yoy_pct ?? null} label="YoY" />
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
        <CardTitle>月次目標と進捗</CardTitle>
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

function ChannelBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'channels'],
    queryFn: fetchChannelBreakdown,
  });
  const total = data.reduce((s, d) => s + d.sessions, 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle>流入経路(過去 30 日)</CardTitle>
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

function AiReferralsBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'ai-referrals'],
    queryFn: () => fetchAiReferrals(30),
  });
  const total = data.reduce((s, d) => s + d.sessions, 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI 経由の流入(過去 30 日)</CardTitle>
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

function ClusterCitationBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'cluster-citation'],
    queryFn: fetchClusterCitation,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>クラスタ別 AI 引用率</CardTitle>
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

function HeatmapBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'heatmap'],
    queryFn: () => fetchHeatmap(5),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI 引用ヒートマップ(主要 5 クエリ × LLM)</CardTitle>
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

function TopQueriesBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'top-queries'],
    queryFn: () => fetchTopQueries(10),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>主要クエリ TOP 10(GSC)</CardTitle>
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
                  <td className="py-1 text-right tabular-nums">
                    {q.ctr === null ? '—' : `${(q.ctr * 100).toFixed(1)}%`}
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

function CompetitorTopBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'competitor-top'],
    queryFn: fetchCompetitorPatternsTop,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>準競合候補 Top 3</CardTitle>
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
          <CardTitle>Next Actions</CardTitle>
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

function PagePerformanceBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'page-performance'],
    queryFn: () => fetchPagePerformance(30, 20),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>記事/ページ別パフォーマンス TOP 20(過去 30 日)</CardTitle>
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
                  <th className="py-1 text-right">順位</th>
                  <th className="py-1 text-right">AI 引用</th>
                </tr>
              </thead>
              <tbody>
                {data.map((p) => (
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
                    <td className="py-1 text-right tabular-nums">
                      {p.avg_position === null ? '—' : p.avg_position.toFixed(1)}
                    </td>
                    <td className="py-1 text-right tabular-nums">{p.citation_count}</td>
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

function FunnelBlock() {
  const { data, isPending } = useQuery({
    queryKey: ['dashboard', 'funnel'],
    queryFn: () => fetchFunnel(90),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>コンバージョン漏斗(過去 90 日)</CardTitle>
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

function KeywordOpportunityBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'keyword-opportunity'],
    queryFn: () => fetchKeywordOpportunity(30, 30),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>キーワード機会マトリクス</CardTitle>
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

function CompetitorContentBlock() {
  const { data = [], isPending } = useQuery({
    queryKey: ['dashboard', 'competitor-content'],
    queryFn: () => fetchCompetitorContent(30, 20),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>競合に引用された記事 TOP 20(過去 30 日)</CardTitle>
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
          <CardTitle>アラート設定</CardTitle>
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
        <CardTitle>月次/週次レポート</CardTitle>
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

export default function DashboardPage() {
  const { data, isPending, error } = useQuery<KpiSummary, Error>({
    queryKey: ['kpi', 'summary', 30],
    queryFn: () => fetchKpiSummary(30),
  });

  const periodHint = data ? `過去 ${data.period_days} 日` : '過去 30 日';

  const overview = (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="AI 引用回数"
          metric={data?.metrics?.ai_citation_count}
          hint={periodHint}
          coverageSince={data?.coverage?.citations_since}
        />
        <KpiCard
          label="オーガニックセッション"
          metric={data?.metrics?.sessions}
          hint={periodHint}
          coverageSince={data?.coverage?.sessions_since}
        />
        <KpiCard
          label="問い合わせ数"
          metric={data?.metrics?.inquiries_count}
          hint={periodHint}
          coverageSince={data?.coverage?.inquiries_since}
        />
        <KpiCard
          label="公開記事数"
          metric={data?.metrics?.contents_published}
          hint={periodHint}
          coverageSince={data?.coverage?.contents_since}
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
          <CardTitle>セッション・引用推移(7 日移動平均 + 異常値ハイライト)</CardTitle>
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
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip />
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
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <ChannelBlock />
        <AiReferralsBlock />
        <ClusterCitationBlock />
      </div>

      <NextActionsBlock />
    </div>
  );

  const contentTab = (
    <div className="space-y-6">
      <PagePerformanceBlock />
      <FunnelBlock />
    </div>
  );

  const keywordTab = (
    <div className="space-y-6">
      <HeatmapBlock />
      <KeywordOpportunityBlock />
      <TopQueriesBlock />
    </div>
  );

  const competitorTab = (
    <div className="space-y-6">
      <CompetitorTopBlock />
      <CompetitorContentBlock />
    </div>
  );

  const settingsTab = (
    <div className="space-y-6">
      <AlertRulesEditor />
      <ReportsBlock />
    </div>
  );

  return (
    <div className="space-y-6">
      <AnomalyBanner />
      <Tabs
        defaultId="overview"
        tabs={[
          { id: 'overview', label: '概要', content: overview },
          { id: 'content', label: 'コンテンツ分析', content: contentTab },
          { id: 'keyword', label: 'キーワード戦略', content: keywordTab },
          { id: 'competitor', label: '競合', content: competitorTab },
          { id: 'settings', label: 'アラート/レポート', content: settingsTab },
        ]}
      />
    </div>
  );
}
