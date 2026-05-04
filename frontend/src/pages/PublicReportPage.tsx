import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { apiClient } from '@/api/client';
import { publicReportPdfUrl, type ReportDetail } from '@/api/reports';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export default function PublicReportPage() {
  const { token = '' } = useParams<{ token: string }>();
  const { data, isPending, error } = useQuery({
    queryKey: ['public-report', token],
    queryFn: async () => {
      const res = await apiClient.get<ReportDetail>(`/public/reports/${token}`);
      return res.data;
    },
    enabled: !!token,
  });

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>
            {data
              ? `${data.report_type === 'monthly' ? '月次' : '週次'}レポート ${data.period}`
              : 'レポート'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <p className="text-sm text-muted-foreground">読み込み中…</p>
          ) : error || !data ? (
            <p className="text-sm text-destructive">
              レポートが見つかりません。共有 URL が無効になっている可能性があります。
            </p>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                生成日時: {new Date(data.generated_at).toLocaleString('ja-JP')}
              </p>
              <a
                href={publicReportPdfUrl(token)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                PDF をダウンロード
              </a>
              <div
                className="prose prose-sm max-w-none text-foreground"
                dangerouslySetInnerHTML={{ __html: data.summary_html ?? '<p>(本文なし)</p>' }}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
