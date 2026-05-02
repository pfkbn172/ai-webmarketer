import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  createCompetitor,
  deleteCompetitor,
  listCompetitors,
  updateCompetitor,
  type Competitor,
  type CompetitorInput,
} from '@/api/competitors';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';

export default function CompetitorsTab() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ['competitors'], queryFn: listCompetitors });
  const [form, setForm] = useState<CompetitorInput>({
    domain: '',
    brand_name: '',
    rss_url: '',
    is_active: true,
  });
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (v: CompetitorInput) => createCompetitor(v),
    onSuccess: () => {
      setForm({ domain: '', brand_name: '', rss_url: '', is_active: true });
      setError(null);
      qc.invalidateQueries({ queryKey: ['competitors'] });
    },
    onError: (e: any) => {
      setError(e?.response?.data?.detail ?? '追加に失敗しました');
    },
  });
  const toggle = useMutation({
    mutationFn: ({ c }: { c: Competitor }) =>
      updateCompetitor(c.id, { ...c, is_active: !c.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['competitors'] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteCompetitor(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['competitors'] }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>競合ドメイン</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            AI 引用モニタで「競合は引用されているがクライアントは引用されていない」を
            判定するための競合サイト一覧。3〜5 社程度を推奨。RSS URL を入れると、
            毎週月曜に競合の最新記事を自動収集します(任意)。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field
            label="ドメイン"
            required
            hint="例: ferret.co.jp(https:// 不要)"
            error={error}
          >
            <Input
              value={form.domain}
              onChange={(e) => setForm({ ...form, domain: e.target.value })}
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="ブランド名" hint="表示用。例: ferret">
              <Input
                value={form.brand_name ?? ''}
                onChange={(e) => setForm({ ...form, brand_name: e.target.value })}
              />
            </Field>
            <Field label="RSS フィード URL" hint="例: https://ferret.co.jp/feed/">
              <Input
                value={form.rss_url ?? ''}
                onChange={(e) => setForm({ ...form, rss_url: e.target.value })}
              />
            </Field>
          </div>
          <Button
            onClick={() => create.mutate(form)}
            disabled={!form.domain.trim() || create.isPending}
          >
            + 競合を追加
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>登録済み(計 {data.length} 件)</CardTitle>
        </CardHeader>
        <CardContent>
          {data.length === 0 ? (
            <p className="text-sm text-muted-foreground">まだ登録されていません</p>
          ) : (
            <ul className="divide-y divide-border">
              {data.map((c: Competitor) => (
                <li key={c.id} className="flex items-center justify-between py-3">
                  <div>
                    <div className="font-medium">{c.brand_name ?? c.domain}</div>
                    <div className="text-xs text-muted-foreground">{c.domain}</div>
                    {c.rss_url && (
                      <div className="text-xs text-muted-foreground">RSS: {c.rss_url}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs ${
                        c.is_active ? 'text-foreground' : 'text-muted-foreground'
                      }`}
                    >
                      {c.is_active ? '有効' : '無効'}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => toggle.mutate({ c })}
                    >
                      {c.is_active ? '無効化' : '有効化'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        if (confirm(`${c.domain} を削除しますか?`)) remove.mutate(c.id);
                      }}
                    >
                      削除
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
