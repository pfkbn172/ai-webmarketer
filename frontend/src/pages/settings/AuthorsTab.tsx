import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  createAuthor,
  deleteAuthor,
  listAuthors,
  updateAuthor,
  type AuthorProfile,
  type AuthorProfileInput,
} from '@/api/authors';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';

const EMPTY: AuthorProfileInput = {
  name: '',
  job_title: '',
  works_for: '',
  alumni_of: [],
  credentials: [],
  expertise: [],
  publications: [],
  speaking_engagements: [],
  awards: [],
  bio_short: '',
  bio_long: '',
  social_profiles: [],
  is_primary: false,
};

function csv(arr: string[]): string {
  return arr.join(', ');
}
function uncsv(s: string): string[] {
  return s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
}

function AuthorForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial: AuthorProfileInput;
  onSubmit: (v: AuthorProfileInput) => void;
  onCancel?: () => void;
  submitLabel: string;
}) {
  const [v, setV] = useState<AuthorProfileInput>(initial);
  const [expertiseStr, setExpertiseStr] = useState(csv(initial.expertise));
  const [credentialsStr, setCredentialsStr] = useState(csv(initial.credentials));
  const [socialStr, setSocialStr] = useState(csv(initial.social_profiles));

  const onSave = () => {
    onSubmit({
      ...v,
      expertise: uncsv(expertiseStr),
      credentials: uncsv(credentialsStr),
      social_profiles: uncsv(socialStr),
    });
  };

  return (
    <div className="space-y-4">
      <Field
        label="名前"
        required
        hint="記事の著者名として表示されます。例: 黄瀬剛志"
      >
        <Input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </Field>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="役職" hint="例: 代表取締役">
          <Input
            value={v.job_title ?? ''}
            onChange={(e) => setV({ ...v, job_title: e.target.value })}
          />
        </Field>
        <Field label="所属組織" hint="例: 株式会社kiseeeen">
          <Input
            value={v.works_for ?? ''}
            onChange={(e) => setV({ ...v, works_for: e.target.value })}
          />
        </Field>
      </div>
      <Field
        label="専門領域"
        hint="カンマ区切りで入力。例: SEO, LLMO, タイ進出支援"
      >
        <Input
          value={expertiseStr}
          onChange={(e) => setExpertiseStr(e.target.value)}
          placeholder="SEO, LLMO, タイ進出"
        />
      </Field>
      <Field
        label="保有資格"
        hint="カンマ区切り。例: 中小企業診断士, 弁護士"
      >
        <Input
          value={credentialsStr}
          onChange={(e) => setCredentialsStr(e.target.value)}
        />
      </Field>
      <Field
        label="SNS / プロフィール URL"
        hint="カンマ区切り。例: https://x.com/foo, https://linkedin.com/in/foo"
      >
        <Input value={socialStr} onChange={(e) => setSocialStr(e.target.value)} />
      </Field>
      <Field label="自己紹介(短文、150 字以内)" hint="検索結果や記事末尾に表示する短い紹介文">
        <Textarea
          value={v.bio_short ?? ''}
          onChange={(e) => setV({ ...v, bio_short: e.target.value })}
          maxLength={200}
          rows={2}
        />
      </Field>
      <Field
        label="経歴詳細(1000 字以内)"
        hint="著者ページ用の詳細経歴。E-E-A-T のシグナルとして AI に伝わる情報源になります"
      >
        <Textarea
          value={v.bio_long ?? ''}
          onChange={(e) => setV({ ...v, bio_long: e.target.value })}
          maxLength={2000}
          rows={4}
        />
      </Field>
      <Field
        label="主著者として設定する"
        hint="この著者を「主著者」にすると、構造化データ(Person スキーマ)や月次レポートで優先的に使われます。テナント内で 1 名まで。"
      >
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={v.is_primary}
            onChange={(e) => setV({ ...v, is_primary: e.target.checked })}
          />
          主著者にする
        </label>
      </Field>
      <div className="flex gap-2 pt-2">
        <Button onClick={onSave} disabled={!v.name.trim()}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            キャンセル
          </Button>
        )}
      </div>
    </div>
  );
}

export default function AuthorsTab() {
  const qc = useQueryClient();
  const { data: authors = [] } = useQuery({ queryKey: ['authors'], queryFn: listAuthors });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const create = useMutation({
    mutationFn: (v: AuthorProfileInput) => createAuthor(v),
    onSuccess: () => {
      setAdding(false);
      qc.invalidateQueries({ queryKey: ['authors'] });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, v }: { id: string; v: AuthorProfileInput }) => updateAuthor(id, v),
    onSuccess: () => {
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ['authors'] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteAuthor(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['authors'] }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>著者プロフィール</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            記事の著者情報。検索エンジンや AI がサイトの信頼性(E-E-A-T)を判断する
            重要なシグナルです。1 人以上、できれば「主著者」を 1 名指定してください。
            記事公開時に Person スキーマとして自動的に <code>&lt;head&gt;</code> へ埋め込まれます。
          </p>
        </CardHeader>
      </Card>

      {authors.map((a: AuthorProfile) =>
        editingId === a.id ? (
          <Card key={a.id}>
            <CardContent className="pt-6">
              <AuthorForm
                initial={{
                  ...a,
                  job_title: a.job_title ?? '',
                  works_for: a.works_for ?? '',
                  bio_short: a.bio_short ?? '',
                  bio_long: a.bio_long ?? '',
                }}
                submitLabel="保存"
                onSubmit={(v) => update.mutate({ id: a.id, v })}
                onCancel={() => setEditingId(null)}
              />
            </CardContent>
          </Card>
        ) : (
          <Card key={a.id}>
            <CardContent className="flex items-center justify-between pt-6">
              <div>
                <div className="font-medium">
                  {a.name}
                  {a.is_primary && (
                    <span className="ml-2 rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      主著者
                    </span>
                  )}
                </div>
                <div className="text-sm text-muted-foreground">
                  {a.job_title ?? '—'} / {a.works_for ?? '—'}
                </div>
                {a.expertise.length > 0 && (
                  <div className="mt-1 text-xs text-muted-foreground">
                    専門: {a.expertise.join(', ')}
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => setEditingId(a.id)}>
                  編集
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    if (confirm(`${a.name} を削除しますか?`)) remove.mutate(a.id);
                  }}
                >
                  削除
                </Button>
              </div>
            </CardContent>
          </Card>
        ),
      )}

      {adding ? (
        <Card>
          <CardHeader>
            <CardTitle>著者を追加</CardTitle>
          </CardHeader>
          <CardContent>
            <AuthorForm
              initial={EMPTY}
              submitLabel="追加"
              onSubmit={(v) => create.mutate(v)}
              onCancel={() => setAdding(false)}
            />
          </CardContent>
        </Card>
      ) : (
        <Button onClick={() => setAdding(true)}>+ 著者を追加</Button>
      )}
    </div>
  );
}
