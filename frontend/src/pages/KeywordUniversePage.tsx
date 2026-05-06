import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { generateBrief } from '@/api/content_briefs';
import {
  listClusterCounts,
  listKeywordUniverse,
  refreshKeywordUniverse,
  type ClusterCount,
  type KeywordUniverseRow,
  type OpportunityFlag,
} from '@/api/keyword_universe';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { Tooltip } from '@/components/ui/Tooltip';
import { computeBreakdown } from '@/lib/priorityScore';

const CLUSTER_LABEL: Record<string, string> = {
  local_hiranoku: '平野区ローカル',
  local_osaka: '大阪・関西ローカル',
  vendor_search: '業者探索',
  dx: 'DX系',
  ai: 'AI系',
  automation: '自動化/RPA系',
  efficiency: '業務効率化・生産性系',
  digitization: 'デジタル化・IT化系',
  subsidy: '補助金・助成金系',
  tool_specific: 'ツール固有名',
  unclassified: '未分類',
};

const OPPORTUNITY_LABEL: Record<string, { label: string; tone: string }> = {
  high_demand_no_coverage: {
    label: '機会大: 派生豊富だが自社未対応',
    tone: 'bg-amber-100 text-amber-900',
  },
  near_top_3: { label: 'TOP3 近い: リライト機会', tone: 'bg-emerald-100 text-emerald-900' },
  low_demand: { label: '需要薄', tone: 'bg-secondary text-muted-foreground' },
};

const FLAG_FILTER_OPTIONS: Array<{ value: OpportunityFlag | ''; label: string }> = [
  { value: '', label: 'すべて' },
  { value: 'high_demand_no_coverage', label: '機会大のみ' },
  { value: 'near_top_3', label: 'TOP3近いのみ' },
];

const fmtPos = (v: number | null) => (v == null ? '—' : v.toFixed(1));
const fmtRate = (v: number | null) =>
  v == null ? '—' : `${(v * 100).toFixed(0)}%`;

export default function KeywordUniversePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [activeCluster, setActiveCluster] = useState<string | null>(null);
  const [flagFilter, setFlagFilter] = useState<OpportunityFlag | ''>('');
  const [minPriority, setMinPriority] = useState(0);
  const [selected, setSelected] = useState<Record<string, KeywordUniverseRow>>({});
  const [primaryKw, setPrimaryKw] = useState<string | null>(null);

  const counts = useQuery<ClusterCount[], Error>({
    queryKey: ['keyword_universe_clusters'],
    queryFn: listClusterCounts,
  });

  const list = useQuery<KeywordUniverseRow[], Error>({
    queryKey: ['keyword_universe', activeCluster, flagFilter, minPriority],
    queryFn: () =>
      listKeywordUniverse({
        cluster_id: activeCluster ?? undefined,
        opportunity_flag: flagFilter || undefined,
        min_priority: minPriority,
        limit: 200,
      }),
  });

  const refresh = useMutation({
    mutationFn: refreshKeywordUniverse,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['keyword_universe'] });
      qc.invalidateQueries({ queryKey: ['keyword_universe_clusters'] });
    },
  });

  const selectedList = useMemo(() => Object.values(selected), [selected]);

  const generate = useMutation({
    mutationFn: () => {
      if (!primaryKw) throw new Error('主軸キーワードを選択してください');
      const primaryRow = selected[primaryKw];
      if (!primaryRow) throw new Error('主軸キーワードが選択リストにありません');
      const relatedIds = selectedList.filter((r) => r.id !== primaryRow.id).map((r) => r.id);
      return generateBrief({
        primary_keyword: primaryRow.keyword,
        related_keyword_ids: relatedIds,
      });
    },
    onSuccess: (brief) => {
      setSelected({});
      setPrimaryKw(null);
      navigate(`/content-briefs/${brief.id}`);
    },
  });

  const toggleSelect = (row: KeywordUniverseRow) => {
    setSelected((prev) => {
      const next = { ...prev };
      if (next[row.id]) {
        delete next[row.id];
        if (primaryKw === row.id) setPrimaryKw(null);
      } else {
        next[row.id] = row;
      }
      return next;
    });
  };

  const totalRows = useMemo(
    () => (counts.data ?? []).reduce((s, c) => s + c.rows, 0),
    [counts.data],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>キーワードユニバース</CardTitle>
          <div className="mt-1 space-y-2 text-sm text-muted-foreground">
            <p>
              GSC実績 / Google・Bingサジェスト派生 / 競合カバー / LLM引用率を統合した
              データ駆動キーワード辞書。スコア欄をホバーすると計算内訳が見られます。
            </p>
            <p className="text-xs">
              <b className="text-amber-700">機会大: 派生豊富だが自社未対応</b>
              =競合も対応していない先行余地。
              <b className="ml-2 text-emerald-700">TOP3 近い: リライト機会</b>
              =既に上位寄りで記事改善で月数十〜数百クリック獲得余地。
              使い方:採用したい行を ☑ でチェック → ◎ で主軸を1つ選ぶ → 上の
              <b>✨ ブリーフ生成</b>でLP/記事の構成案を作成できます。
            </p>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
          >
            {refresh.isPending ? '集計中…' : '🔄 いま集計し直す'}
          </Button>
          {refresh.data && (
            <span className="text-sm text-muted-foreground">
              {refresh.data.upserted} 件更新
            </span>
          )}
          <span className="ml-auto text-xs text-muted-foreground">
            総件数: {totalRows.toLocaleString()}
          </span>
        </CardContent>
      </Card>

      {/* クラスタタブ */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">クラスタ別フィルタ</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <ClusterPill
            label="すべて"
            count={totalRows}
            active={activeCluster === null}
            onClick={() => setActiveCluster(null)}
          />
          {(counts.data ?? []).map((c) => (
            <ClusterPill
              key={c.cluster_id}
              label={CLUSTER_LABEL[c.cluster_id] ?? c.cluster_id}
              count={c.rows}
              active={activeCluster === c.cluster_id}
              onClick={() => setActiveCluster(c.cluster_id)}
            />
          ))}
        </CardContent>
      </Card>

      {/* セカンダリフィルタ */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 py-4">
          <label className="text-sm">
            機会フラグ:&nbsp;
            <select
              className="rounded border px-2 py-1 text-sm"
              value={flagFilter ?? ''}
              onChange={(e) => setFlagFilter((e.target.value || '') as OpportunityFlag | '')}
            >
              {FLAG_FILTER_OPTIONS.map((o) => (
                <option key={String(o.value ?? 'all')} value={o.value ?? ''}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            最低 priority_score:&nbsp;
            <input
              type="number"
              min={0}
              step={5}
              value={minPriority}
              onChange={(e) => setMinPriority(Number(e.target.value) || 0)}
              className="w-20 rounded border px-2 py-1 text-sm"
            />
          </label>
        </CardContent>
      </Card>

      {/* 選択バー */}
      {selectedList.length > 0 && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3 py-4">
            <span className="text-sm font-medium">
              選択中 {selectedList.length} 件:
            </span>
            <div className="flex flex-wrap gap-1">
              {selectedList.map((r) => (
                <span
                  key={r.id}
                  className={`rounded px-2 py-0.5 text-xs ${
                    primaryKw === r.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-secondary-foreground'
                  }`}
                >
                  {r.keyword}
                  {primaryKw === r.id ? ' (主軸)' : ''}
                </span>
              ))}
            </div>
            <Button
              className="ml-auto"
              disabled={!primaryKw || generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? '生成中…' : '✨ ブリーフ生成'}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setSelected({});
                setPrimaryKw(null);
              }}
            >
              クリア
            </Button>
            {!primaryKw && (
              <p className="w-full text-xs text-amber-700">
                テーブル左端の「主軸」ボタンで主軸キーワードを1つ選んでください。
              </p>
            )}
            {generate.isError && (
              <p className="w-full text-xs text-red-600">
                {(generate.error as Error)?.message ?? 'ブリーフ生成に失敗しました'}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* テーブル */}
      <Card>
        <CardContent className="overflow-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-2 text-center">採用</th>
                <th className="px-2 py-2 text-center">主軸</th>
                <th className="px-4 py-2">キーワード</th>
                <th className="px-4 py-2">クラスタ</th>
                <th className="px-4 py-2 text-right">スコア</th>
                <th className="px-4 py-2 text-right">imp(12m)</th>
                <th className="px-4 py-2 text-right">avg pos</th>
                <th className="px-4 py-2 text-right">派生</th>
                <th className="px-4 py-2 text-right">競合</th>
                <th className="px-4 py-2 text-right">LLM自社</th>
                <th className="px-4 py-2">機会</th>
              </tr>
            </thead>
            <tbody>
              {list.isPending && (
                <tr>
                  <td colSpan={11} className="p-0">
                    <TableSkeleton rows={8} cols={9} />
                  </td>
                </tr>
              )}
              {list.data?.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-muted-foreground">
                    該当キーワードがありません
                  </td>
                </tr>
              )}
              {list.data?.map((r) => {
                const flagInfo = r.opportunity_flag
                  ? OPPORTUNITY_LABEL[r.opportunity_flag]
                  : null;
                const isSelected = !!selected[r.id];
                const isPrimary = primaryKw === r.id;
                return (
                  <tr key={r.id} className="border-t border-border hover:bg-muted/50">
                    <td className="px-2 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(r)}
                      />
                    </td>
                    <td className="px-2 py-2 text-center">
                      <input
                        type="radio"
                        name="primary-keyword"
                        disabled={!isSelected}
                        checked={isPrimary}
                        onChange={() => setPrimaryKw(r.id)}
                      />
                    </td>
                    <td className="px-4 py-2 font-medium">{r.keyword}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.cluster_ids.map((cid) => (
                          <span
                            key={cid}
                            className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
                          >
                            {CLUSTER_LABEL[cid] ?? cid}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      <PriorityScoreCell row={r} />
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.gsc_imp_12m.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmtPos(r.gsc_avg_position)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.suggest_derivative_count}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.competitor_coverage_count}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {fmtRate(r.llm_self_cite_rate)}
                    </td>
                    <td className="px-4 py-2">
                      {flagInfo ? (
                        <span className={`inline-block rounded px-2 py-0.5 text-xs ${flagInfo.tone}`}>
                          {flagInfo.label}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground/60">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function PriorityScoreCell({ row }: { row: KeywordUniverseRow }) {
  const breakdown = computeBreakdown({
    gsc_imp_12m: row.gsc_imp_12m,
    gsc_avg_position: row.gsc_avg_position,
    suggest_derivative_count: row.suggest_derivative_count,
    competitor_coverage_count: row.competitor_coverage_count,
    llm_self_cite_rate: row.llm_self_cite_rate,
    is_geographic: row.is_geographic,
  });
  const tooltipBody = (
    <div className="space-y-1">
      <div className="font-semibold text-slate-100">priority_score の内訳</div>
      <BreakdownRow label="GSC実需 log10(imp+1) × 30" value={breakdown.imp_score} />
      <BreakdownRow label="サジェスト派生 log10(n+1) × 20" value={breakdown.derivative_score} />
      <BreakdownRow label="競合カバー × 5" value={breakdown.competitor_score} />
      <BreakdownRow label="順位上位寄り (51-pos) × 0.5" value={breakdown.position_score} />
      <BreakdownRow
        label="LLM未引用機会 (1-self_cite) × 10"
        value={breakdown.llm_opportunity_score}
      />
      {breakdown.geo_penalty !== 0 && (
        <BreakdownRow label="地域系で実需薄 (penalty)" value={breakdown.geo_penalty} />
      )}
      <div className="mt-1 border-t border-slate-700 pt-1 font-semibold">
        合計 {breakdown.total.toFixed(2)}
      </div>
    </div>
  );
  return (
    <Tooltip content={tooltipBody}>
      <span className="cursor-help underline decoration-dotted underline-offset-4">
        {Number(row.priority_score).toFixed(1)}
      </span>
    </Tooltip>
  );
}

function BreakdownRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-300">{label}</span>
      <span className="tabular-nums">{value >= 0 ? '+' : ''}{value.toFixed(2)}</span>
    </div>
  );
}

function ClusterPill({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs transition ${
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-card text-card-foreground hover:bg-muted'
      }`}
    >
      {label}
      <span className="ml-1 text-[11px] opacity-80">{count.toLocaleString()}</span>
    </button>
  );
}
