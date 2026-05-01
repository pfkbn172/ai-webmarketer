import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  createQuery,
  deleteQuery,
  listQueries,
  type TargetQuery,
} from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

export default function TargetQueriesPage() {
  const qc = useQueryClient();
  const { data, isPending } = useQuery<TargetQuery[], Error>({
    queryKey: ['target_queries'],
    queryFn: listQueries,
  });
  const [text, setText] = useState('');
  const create = useMutation({
    mutationFn: () => createQuery({ query_text: text }),
    onSuccess: () => {
      setText('');
      qc.invalidateQueries({ queryKey: ['target_queries'] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteQuery(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['target_queries'] }),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>ターゲットクエリ</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) create.mutate();
            }}
          >
            <Input
              placeholder="新しいクエリを入力(例: AIウェブマーケター)"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <Button type="submit" disabled={create.isPending || !text.trim()}>
              追加
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>登録済みクエリ</CardTitle>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <p className="text-sm text-muted-foreground">読み込み中…</p>
          ) : data && data.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.map((q) => (
                <li key={q.id} className="flex items-center justify-between py-2">
                  <div>
                    <div className="text-sm">{q.query_text}</div>
                    <div className="text-xs text-muted-foreground">
                      cluster: {q.cluster_id ?? '—'} / priority: {q.priority} / active:{' '}
                      {q.is_active ? 'Y' : 'N'}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove.mutate(q.id)}
                    disabled={remove.isPending}
                  >
                    削除
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">クエリ未登録</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
