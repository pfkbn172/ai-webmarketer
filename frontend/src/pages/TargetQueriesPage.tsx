import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  createQuery,
  deleteQuery,
  listQueries,
  type TargetQuery,
} from '@/api/queries';
import {
  bulkAdoptQueries,
  suggestQueries,
  type QuerySuggestion,
} from '@/api/query_suggestion';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

const CLUSTER_LABEL: Record<string, string> = {
  local_district: '拠点地域',
  local_expand: '拡大目標地域',
  unique_value: '独自性活用',
  competitive: '比較・観測',
  industry_test: '業種特化テスト',
};

export default function TargetQueriesPage() {
  const qc = useQueryClient();
  const { data, isPending } = useQuery<TargetQuery[], Error>({
    queryKey: ['target_queries'],
    queryFn: listQueries,
  });
  const [text, setText] = useState('');
  const [suggestions, setSuggestions] = useState<QuerySuggestion[]>([]);

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
  const ai = useMutation({
    mutationFn: () => suggestQueries(),
    onSuccess: (v) => setSuggestions(v),
  });
  const adopt = useMutation({
    mutationFn: (qs: QuerySuggestion[]) => bulkAdoptQueries(qs),
    onSuccess: () => {
      setSuggestions([]);
      qc.invalidateQueries({ queryKey: ['target_queries'] });
    },
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>ターゲットクエリ</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            AI 引用モニタの対象クエリ(最大 20 本)。<b>事業情報を埋めた上で「✨ AI に提案させる」</b>を
            使うと、勝てる確度の高いクエリを業界・地域・規模に合わせて 15〜20 本提案します。
          </p>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>✨ AI にクエリを提案させる</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            設定 →「事業情報」タブを埋めてから実行すると、事業ステージ・拠点地域・独自性を
            踏まえたクエリリストが返ります。気に入ったものだけ採用できます。
          </p>
        </CardHeader>
        <CardContent>
          <Button onClick={() => ai.mutate()} disabled={ai.isPending}>
            {ai.isPending ? 'AI 解析中…' : 'AI に 15〜20 本提案させる'}
          </Button>
          {ai.isError && (
            <p className="mt-2 text-sm text-destructive">
              提案失敗: {(ai.error as any)?.response?.data?.detail ?? '不明'}
            </p>
          )}
        </CardContent>
      </Card>

      {suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>AI からの提案({suggestions.length} 件)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex gap-2">
              <Button onClick={() => adopt.mutate(suggestions)} disabled={adopt.isPending}>
                すべて採用
              </Button>
              <Button variant="ghost" onClick={() => setSuggestions([])}>
                破棄
              </Button>
            </div>
            <ul className="divide-y divide-border">
              {suggestions.map((s, i) => (
                <li key={i} className="space-y-1 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{s.query_text}</div>
                      <div className="text-xs text-muted-foreground">
                        cluster: {CLUSTER_LABEL[s.cluster_id ?? ''] ?? s.cluster_id ?? '—'} /
                        priority: {s.priority} / 期待: {s.expected_conversion}
                      </div>
                      {s.search_intent && (
                        <div className="text-xs text-muted-foreground">
                          意図: {s.search_intent}
                        </div>
                      )}
                      {s.reasoning && (
                        <div className="text-xs text-muted-foreground">
                          根拠: {s.reasoning}
                        </div>
                      )}
                    </div>
                    <Button
                      size="sm"
                      onClick={() => adopt.mutate([s])}
                      disabled={adopt.isPending}
                    >
                      採用
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>手動で 1 件追加</CardTitle>
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
              placeholder="新しいクエリを入力(例: 天王寺区 IT DX サポート)"
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
          <CardTitle>登録済みクエリ({data?.length ?? 0} 件)</CardTitle>
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
                      cluster: {CLUSTER_LABEL[q.cluster_id ?? ''] ?? q.cluster_id ?? '—'} /
                      priority: {q.priority} / active: {q.is_active ? 'Y' : 'N'}
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
