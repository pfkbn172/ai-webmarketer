import { useQuery } from '@tanstack/react-query';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fetchKpiSummary, type KpiSummary } from '@/api/kpi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tabular-nums">{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isPending, error } = useQuery<KpiSummary, Error>({
    queryKey: ['kpi', 'summary', 30],
    queryFn: () => fetchKpiSummary(30),
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="AI 引用回数"
          value={data?.ai_citation_count ?? '—'}
          hint="過去 30 日"
        />
        <KpiCard label="オーガニックセッション" value={data?.sessions ?? '—'} hint="過去 30 日" />
        <KpiCard label="問い合わせ数" value={data?.inquiries_count ?? '—'} hint="過去 30 日" />
        <KpiCard label="公開記事数" value={data?.contents_published ?? '—'} hint="過去 30 日" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>セッション・引用推移</CardTitle>
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
            <ResponsiveContainer width="100%" height={260}>
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
    </div>
  );
}
