/**
 * 戦略レビュー画面。
 * - 違和感アラート(自動検知)
 * - AI 戦略レビュー(オンデマンド)
 * - 戦略軸 A/B 比較(プローブループ)
 * - 競合パターン分析
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchAnomalies,
  fetchCompetitorPatterns,
  fetchLatestProbeLoop,
  fetchLatestReview,
  runProbeLoop,
  runReview,
  type Anomaly,
  type CompetitorPattern,
  type ProbeLoopResult,
  type StoredRecord,
  type StrategicReview,
} from '@/api/strategic';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

function _formatGeneratedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const SEVERITY_COLOR: Record<string, string> = {
  high: 'text-destructive',
  medium: 'text-foreground',
  low: 'text-muted-foreground',
};

function AnomalyList() {
  const { data = [], isPending } = useQuery({
    queryKey: ['strategic', 'anomalies'],
    queryFn: fetchAnomalies,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>違和感アラート(自動検知)</CardTitle>
        <p className="mt-1 text-sm text-muted-foreground">
          数値の急変だけでなく「事業ステージとクエリ広域度のミスマッチ」「全クエリで自社引用 0 が
          続いている」など、戦略的な違和感も検知します。
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">違和感は検知されていません(良好)</p>
        ) : (
          <ul className="space-y-2">
            {data.map((a: Anomaly, i: number) => (
              <li key={i} className={`text-sm ${SEVERITY_COLOR[a.severity]}`}>
                <span className="rounded border border-border px-2 py-0.5 text-xs">
                  {a.severity}
                </span>{' '}
                <b>{a.kind}</b>: {a.detail}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ReviewBox() {
  const qc = useQueryClient();
  const { data: stored, isPending: loadingStored } = useQuery({
    queryKey: ['strategic', 'review', 'latest'],
    queryFn: fetchLatestReview,
  });
  const review = useMutation<StoredRecord<StrategicReview>, Error>({
    mutationFn: runReview,
    onSuccess: (rec) => qc.setQueryData(['strategic', 'review', 'latest'], rec),
  });

  const record = review.data ?? stored;
  const result = record?.result;

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI 戦略レビュー(月次レポートと別、いつでも実行可能)</CardTitle>
        <p className="mt-1 text-sm text-muted-foreground">
          事業文脈と直近 30 日の数字を突き合わせ、構造的な発見と次のアクションを提示します。
          毎月 3 日の月次レポート生成時にも自動で更新されます。
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => review.mutate()} disabled={review.isPending}>
            {review.isPending
              ? '生成中…(30〜60 秒)'
              : record
                ? '再生成'
                : '今すぐ戦略レビュー'}
          </Button>
          {record?.generated_at && (
            <span className="text-xs text-muted-foreground">
              最終生成: {_formatGeneratedAt(record.generated_at)}
            </span>
          )}
          {!record && loadingStored && (
            <span className="text-xs text-muted-foreground">前回結果を読み込み中…</span>
          )}
        </div>
        {result && (
          <div className="space-y-3 text-sm">
            <Section title="構造的な発見" items={result.core_findings ?? []} />
            <Section
              title="事業文脈と整合している点"
              items={result.alignments_with_business_context ?? []}
            />
            <Section title="ずれている兆候" items={result.misalignments ?? []} />
            {(result.next_actions ?? []).length > 0 && (
              <div>
                <h4 className="font-semibold">推奨アクション</h4>
                <ol className="mt-1 list-decimal space-y-2 pl-5">
                  {result.next_actions!.map((a, i) => (
                    <li key={i}>
                      <div>{a.action}</div>
                      <div className="text-xs text-muted-foreground">根拠: {a.rationale}</div>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}
        {!result && !loadingStored && !review.isPending && (
          <p className="text-xs text-muted-foreground">
            まだ戦略レビューが実行されていません。「今すぐ戦略レビュー」を押すか、月次レポート生成(毎月 3 日)を待ってください。
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="font-semibold">{title}</h4>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}

function ProbeLoopBox() {
  const qc = useQueryClient();
  const { data: stored, isPending: loadingStored } = useQuery({
    queryKey: ['strategic', 'probe-loop', 'latest'],
    queryFn: fetchLatestProbeLoop,
  });
  const probe = useMutation<StoredRecord<ProbeLoopResult>, Error>({
    mutationFn: runProbeLoop,
    onSuccess: (rec) => qc.setQueryData(['strategic', 'probe-loop', 'latest'], rec),
  });

  const record = probe.data ?? stored;
  const result = record?.result;

  return (
    <Card>
      <CardHeader>
        <CardTitle>戦略軸 A/B 比較</CardTitle>
        <p className="mt-1 text-sm text-muted-foreground">
          「業種特化」と「地域 × IT/DX サポート」のような戦略軸の引用獲得期待値を
          AI に推論比較させ、勝者と推奨クエリを返します。月次レポート生成時にも自動更新されます。
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => probe.mutate()} disabled={probe.isPending}>
            {probe.isPending ? '比較中…' : record ? '再比較' : '比較を実行'}
          </Button>
          {record?.generated_at && (
            <span className="text-xs text-muted-foreground">
              最終生成: {_formatGeneratedAt(record.generated_at)}
            </span>
          )}
          {!record && loadingStored && (
            <span className="text-xs text-muted-foreground">前回結果を読み込み中…</span>
          )}
        </div>
        {result && (
          <div className="grid gap-3 md:grid-cols-2 text-sm">
            <AxisCard label="軸 A" axis={result.axis_a} winner={result.winner === 'axis_a'} />
            <AxisCard label="軸 B" axis={result.axis_b} winner={result.winner === 'axis_b'} />
            {result.winner_rationale && (
              <div className="md:col-span-2 rounded-md border border-border bg-muted p-3">
                <div className="font-semibold">勝者の理由</div>
                <p className="mt-1 text-muted-foreground">{result.winner_rationale}</p>
              </div>
            )}
          </div>
        )}
        {!result && !loadingStored && !probe.isPending && (
          <p className="text-xs text-muted-foreground">
            まだ比較が実行されていません。「比較を実行」を押すか、月次レポート生成を待ってください。
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function AxisCard({
  label,
  axis,
  winner,
}: {
  label: string;
  axis?: ProbeLoopResult['axis_a'];
  winner: boolean;
}) {
  if (!axis) return null;
  return (
    <div
      className={`rounded-md border p-3 ${
        winner ? 'border-primary bg-primary/5' : 'border-border'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="font-semibold">{label}: {axis.label}</div>
        {winner && <span className="rounded bg-primary px-2 py-0.5 text-xs text-primary-foreground">勝者</span>}
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        期待引用率: {(axis.expected_self_citation_rate * 100).toFixed(0)}% / 競合: {axis.competitive_strength} / ステージ適合: {axis.stage_fit}
      </div>
      <p className="mt-2">{axis.reasoning}</p>
      <div className="mt-2">
        <div className="font-semibold text-xs">サンプルクエリ</div>
        <ul className="ml-4 list-disc text-xs text-muted-foreground">
          {axis.sample_queries.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function CompetitorBox() {
  const { data = [], isPending } = useQuery({
    queryKey: ['strategic', 'competitor-patterns'],
    queryFn: () => fetchCompetitorPatterns(30),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>競合パターン分析(citation_logs 頻出ドメイン)</CardTitle>
        <p className="mt-1 text-sm text-muted-foreground">
          引用ログの全 URL から頻出ドメインを集計。「未登録だが頻出 = 準競合候補」を可視化します。
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中…</p>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground">引用ログが少なく抽出できませんでした</p>
        ) : (
          <ul className="space-y-1">
            {data.map((d: CompetitorPattern) => (
              <li key={d.domain} className="flex items-center gap-2 text-sm">
                <span
                  className={`rounded border px-2 py-0.5 text-xs ${
                    d.label === 'candidate'
                      ? 'border-primary text-primary'
                      : d.label === 'registered_competitor'
                      ? 'border-foreground text-foreground'
                      : 'border-muted text-muted-foreground'
                  }`}
                >
                  {d.label === 'candidate'
                    ? '準競合候補'
                    : d.label === 'registered_competitor'
                    ? '登録済'
                    : '除外'}
                </span>
                <span className="font-mono">{d.domain}</span>
                <span className="text-xs text-muted-foreground">({d.count} 回)</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function StrategicReviewPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>戦略レビュー</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            AI が「プロのマーケター視点」で事業実態と数字を突き合わせ、構造的な発見と
            次のアクションを提案するページです。事業情報(設定 → 事業情報タブ)を
            充実させるほど提言の質が上がります。
          </p>
        </CardHeader>
      </Card>

      <AnomalyList />
      <ReviewBox />
      <ProbeLoopBox />
      <CompetitorBox />
    </div>
  );
}
