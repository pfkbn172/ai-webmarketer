import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { deleteBrief, listBriefs, type ContentBrief } from '@/api/content_briefs';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import { TableSkeleton } from '@/components/ui/Skeleton';

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  draft: { label: '下書き', tone: 'bg-slate-100 text-slate-700' },
  adopted: { label: 'WP送信済', tone: 'bg-emerald-100 text-emerald-800' },
  published: { label: '公開済', tone: 'bg-blue-100 text-blue-800' },
};

export default function ContentBriefsPage() {
  const qc = useQueryClient();
  const dialog = useConfirm();
  const list = useQuery<ContentBrief[], Error>({
    queryKey: ['content_briefs'],
    queryFn: () => listBriefs(),
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteBrief(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['content_briefs'] }),
  });

  const askDelete = async (b: ContentBrief) => {
    const ok = await dialog.confirm({
      title: 'ブリーフを削除しますか?',
      message: `「${b.title}」を完全に削除します。この操作は取り消せません。`,
      confirmLabel: '削除',
      destructive: true,
    });
    if (ok) remove.mutate(b.id);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>コンテンツブリーフ</CardTitle>
          <div className="mt-1 space-y-2 text-sm text-muted-foreground">
            <p>
              採用キーワードから AI が生成した LP/記事の構成案(title /
              meta_description / h2 5本 / 関連語 / 推奨URL)。
            </p>
            <p className="text-xs">
              使い方:
              <b className="ml-1">①</b>
              <a className="text-primary underline mx-1" href="/marketer/strategy/universe">
                キーワード分析
              </a>
              で行を選び <b>✨ ブリーフ生成</b> →
              <b className="ml-1">②</b>
              タイトルクリックで詳細を確認 →
              <b className="ml-1">③</b>
              「📝 WordPress下書きにする」で WP の下書きとして配置。
              本文は WP 側で書き起こします(プレースホルダ + h2 構成 + meta コメントが入った状態)。
            </p>
          </div>
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
                  <td colSpan={7} className="p-0">
                    <TableSkeleton rows={5} cols={6} />
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
                      <Button variant="secondary" onClick={() => askDelete(b)}>
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
      {dialog.element}
    </div>
  );
}
