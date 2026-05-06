import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { deleteBrief, listBriefs, type ContentBrief } from '@/api/content_briefs';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  draft: { label: '下書き', tone: 'bg-slate-100 text-slate-700' },
  adopted: { label: 'WP送信済', tone: 'bg-emerald-100 text-emerald-800' },
  published: { label: '公開済', tone: 'bg-blue-100 text-blue-800' },
};

export default function ContentBriefsPage() {
  const qc = useQueryClient();
  const list = useQuery<ContentBrief[], Error>({
    queryKey: ['content_briefs'],
    queryFn: () => listBriefs(),
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteBrief(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['content_briefs'] }),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>コンテンツブリーフ</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            キーワード分析画面で採用したキーワード群から AI が生成した
            LP/記事の構成案。<b>「ブリーフ詳細」</b>から WordPress 下書きを作成できます。
          </p>
        </CardHeader>
      </Card>

      <Card>
        <CardContent className="overflow-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">タイトル</th>
                <th className="px-4 py-2">主軸キーワード</th>
                <th className="px-4 py-2">クラスタ</th>
                <th className="px-4 py-2 text-right">h2 数</th>
                <th className="px-4 py-2">状態</th>
                <th className="px-4 py-2">作成日時</th>
                <th className="px-4 py-2 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {list.isPending && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    読込中…
                  </td>
                </tr>
              )}
              {list.data?.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    まだブリーフがありません。「キーワード分析」画面でキーワードを採用して生成してください。
                  </td>
                </tr>
              )}
              {list.data?.map((b) => {
                const status = STATUS_LABEL[b.status] ?? STATUS_LABEL.draft;
                return (
                  <tr key={b.id} className="border-t hover:bg-slate-50">
                    <td className="px-4 py-2 font-medium">
                      <Link to={`/content-briefs/${b.id}`} className="text-blue-700 hover:underline">
                        {b.title}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{b.primary_keyword}</td>
                    <td className="px-4 py-2 text-xs text-slate-600">
                      {b.cluster_ids.join(', ')}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {b.h2_outline.length}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs ${status.tone}`}>
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {new Date(b.created_at).toLocaleString('ja-JP')}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button
                        variant="secondary"
                        onClick={() => {
                          if (confirm('削除しますか?')) remove.mutate(b.id);
                        }}
                      >
                        削除
                      </Button>
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
