import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import {
  getHomeToday,
  regenerateToday,
  type HomeToday,
  type Severity,
  type TodayAction,
} from '@/api/home';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { CardSkeleton, Skeleton } from '@/components/ui/Skeleton';

const SEVERITY_TONE: Record<Severity, string> = {
  red: 'border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950/50 dark:text-rose-100',
  yellow:
    'border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-100',
  green:
    'border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100',
};
const SEVERITY_DOT: Record<Severity, string> = {
  red: '🔴',
  yellow: '🟡',
  green: '🟢',
};

const fmtDelta = (curr: number, prev: number) => {
  if (prev === 0) return curr > 0 ? '+∞%' : '±0%';
  const pct = Math.round(((curr - prev) / prev) * 100);
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct}%`;
};

const fmtRate = (v: number | null) =>
  v == null ? '—' : `${Math.round(v * 100)}%`;

const fmtDateTime = (iso: string) => new Date(iso).toLocaleString('ja-JP');

export default function HomePage() {
  const qc = useQueryClient();
  const today = useQuery<HomeToday, Error>({
    queryKey: ['home_today'],
    queryFn: getHomeToday,
  });
  const regen = useMutation({
    mutationFn: regenerateToday,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['home_today'] }),
  });

  if (today.isPending) {
    return (
      <div className="space-y-6">
        <Card>
          <CardSkeleton lines={4} />
        </Card>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-2 py-4">
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-7 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }
  if (today.isError || !today.data) {
    return <div className="p-8 text-center text-red-600">読み込みに失敗しました</div>;
  }
  const data = today.data;

  return (
    <div className="space-y-6">
      {/* 今日の3アクション */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2">
          <div>
            <CardTitle>今日の3つのアクション</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {data.actions_generated_at
                ? `最終生成: ${fmtDateTime(data.actions_generated_at)}`
                : 'まだ生成されていません'}
              {data.actions_stale && data.actions.length > 0 ? ' (要再生成)' : ''}
              <span className="ml-2">
                毎朝 6:45 JST に自動生成。「実行する →」で該当画面へ直接ジャンプ。
              </span>
            </p>
          </div>
          <Button onClick={() => regen.mutate()} disabled={regen.isPending}>
            {regen.isPending ? '生成中…' : '🔄 今すぐ再生成'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.actions.length === 0 && (
            <p className="text-sm text-muted-foreground">
              まだアクションが生成されていません。「今すぐ再生成」を押してください。
            </p>
          )}
          {data.actions.map((a) => (
            <ActionRow key={a.id} action={a} />
          ))}
          {regen.isError && (
            <p className="text-sm text-red-600">
              再生成に失敗しました: {(regen.error as Error)?.message}
            </p>
          )}
        </CardContent>
      </Card>

      {/* KPIサマリー */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard
          label="AI流入セッション(7日)"
          value={data.kpi.ai_referral_sessions_7d.toLocaleString()}
          delta={fmtDelta(
            data.kpi.ai_referral_sessions_7d,
            data.kpi.ai_referral_sessions_prev_7d,
          )}
        />
        <KpiCard
          label="自社引用率(30日)"
          value={fmtRate(data.kpi.self_cite_rate_30d)}
        />
        <KpiCard
          label="問合せ件数(30日)"
          value={data.kpi.inquiries_30d.toLocaleString()}
          warning={data.kpi.inquiries_30d === 0}
        />
        <KpiCard
          label="キーワード機会数"
          value={data.kpi.opportunity_count.toLocaleString()}
        />
      </div>

      {/* システム健全性(問題があるときだけ) */}
      {data.health.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">⚠ システム健全性</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.health.map((h, i) => (
              <div
                key={i}
                className={`flex items-center justify-between rounded border px-3 py-2 text-sm ${
                  h.severity === 'error'
                    ? 'border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950/50 dark:text-rose-100'
                    : 'border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-100'
                }`}
              >
                <span>{h.message}</span>
                {h.target_url && (
                  <Link className="text-primary hover:underline" to={h.target_url}>
                    対応する →
                  </Link>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 最近の更新 */}
      {data.recent_updates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">最近の更新</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {data.recent_updates.map((r, i) => (
                <li key={i} className="flex justify-between gap-3">
                  <span>
                    {r.target_url ? (
                      <Link className="text-primary hover:underline" to={r.target_url}>
                        {r.title}
                      </Link>
                    ) : (
                      r.title
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {fmtDateTime(r.when)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ActionRow({ action }: { action: TodayAction }) {
  const tone = SEVERITY_TONE[action.severity];
  return (
    <div className={`rounded border-l-4 p-3 ${tone}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="font-semibold">
            {SEVERITY_DOT[action.severity]} #{action.action_index}: {action.title}
          </div>
          {action.rationale && (
            <p className="text-xs opacity-80">{action.rationale}</p>
          )}
          {action.related_keyword && (
            <span className="inline-block rounded bg-background/60 px-1.5 py-0.5 text-xs">
              {action.related_keyword}
            </span>
          )}
        </div>
        {action.target_url && (
          <Link
            to={action.target_url}
            className="shrink-0 rounded border border-current px-3 py-1 text-xs hover:bg-background/60"
          >
            実行する →
          </Link>
        )}
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  delta,
  warning,
}: {
  label: string;
  value: string;
  delta?: string;
  warning?: boolean;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`mt-1 text-2xl font-bold tabular-nums ${warning ? 'text-amber-700 dark:text-amber-300' : ''}`}>
          {value}
        </div>
        {delta && (
          <div className="mt-1 text-xs text-muted-foreground">{delta}</div>
        )}
      </CardContent>
    </Card>
  );
}
