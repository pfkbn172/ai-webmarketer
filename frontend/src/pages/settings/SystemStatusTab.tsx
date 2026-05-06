import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { listJobs, type JobLog } from '@/api/system_status';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

const STATUS_TONE: Record<JobLog['status'], string> = {
  success: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-rose-100 text-rose-900',
  running: 'bg-amber-100 text-amber-900',
};

const fmtDt = (iso: string) => new Date(iso).toLocaleString('ja-JP');
const fmtDur = (s: number | null) => (s == null ? '—' : `${s}秒`);

export default function SystemStatusTab() {
  const [hours, setHours] = useState(72);
  const { data, isPending, refetch, isFetching } = useQuery<JobLog[], Error>({
    queryKey: ['system_jobs', hours],
    queryFn: () => listJobs(hours, 200),
  });

  const total = data?.length ?? 0;
  const failed = data?.filter((j) => j.status === 'failed').length ?? 0;
  const running = data?.filter((j) => j.status === 'running').length ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base">ジョブ実行履歴</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            直近 {hours} 時間で記録されたジョブの実行状況。失敗が継続する場合は
            認証情報や API キーを確認してください。
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <select
            className="rounded border px-2 py-1"
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          >
            <option value={24}>過去 24 時間</option>
            <option value={72}>過去 72 時間</option>
            <option value={168}>過去 7 日間</option>
          </select>
          <button
            type="button"
            className="rounded border px-2 py-1"
            disabled={isFetching}
            onClick={() => refetch()}
          >
            {isFetching ? '更新中…' : '🔄 再読込'}
          </button>
        </div>
      </CardHeader>
      <CardContent className="overflow-auto p-0">
        <div className="flex flex-wrap gap-3 px-4 py-3 text-xs text-muted-foreground">
          <span>件数: {total}</span>
          <span className={failed > 0 ? 'text-rose-700' : ''}>失敗: {failed}</span>
          <span>実行中: {running}</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">ジョブ名</th>
              <th className="px-4 py-2">状態</th>
              <th className="px-4 py-2">開始</th>
              <th className="px-4 py-2">終了</th>
              <th className="px-4 py-2 text-right">所要</th>
              <th className="px-4 py-2">エラー</th>
            </tr>
          </thead>
          <tbody>
            {isPending && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  読込中…
                </td>
              </tr>
            )}
            {data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  該当期間にジョブ履歴はありません
                </td>
              </tr>
            )}
            {data?.map((j) => (
              <tr key={j.id} className="border-t hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">{j.job_name}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded px-2 py-0.5 text-xs ${STATUS_TONE[j.status]}`}>
                    {j.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs">{fmtDt(j.started_at)}</td>
                <td className="px-4 py-2 text-xs">{j.finished_at ? fmtDt(j.finished_at) : '—'}</td>
                <td className="px-4 py-2 text-right tabular-nums text-xs">
                  {fmtDur(j.duration_seconds)}
                </td>
                <td className="px-4 py-2 text-xs text-rose-700">
                  {j.error_text ? j.error_text.slice(0, 80) : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
