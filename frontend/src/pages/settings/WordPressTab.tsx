import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  deleteCredential,
  listCredentials,
  upsertCredential,
} from '@/api/credentials';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';

export default function WordPressTab() {
  const qc = useQueryClient();
  const { data: creds = [] } = useQuery({
    queryKey: ['credentials'],
    queryFn: listCredentials,
  });
  const wp = creds.find((c) => c.provider === 'wordpress');

  const [baseUrl, setBaseUrl] = useState('');
  const [userLogin, setUserLogin] = useState('');
  const [appPassword, setAppPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const upsert = useMutation({
    mutationFn: () =>
      upsertCredential('wordpress', {
        base_url: baseUrl,
        user_login: userLogin,
        app_password: appPassword,
      }),
    onSuccess: () => {
      setError(null);
      setBaseUrl('');
      setUserLogin('');
      setAppPassword('');
      qc.invalidateQueries({ queryKey: ['credentials'] });
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? '保存に失敗しました'),
  });
  const remove = useMutation({
    mutationFn: () => deleteCredential('wordpress'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>WordPress 連携</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            WordPress に記事を公開した際、自動で構造化データ(JSON-LD)を埋め込んだり、
            llms.txt を更新するために使います。
          </p>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-border bg-muted p-4 text-sm">
            <h4 className="font-semibold">設定の手順(初めての方)</h4>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted-foreground">
              <li>
                WordPress 管理画面にログイン → 左メニュー「ユーザー」→ 自分のプロフィール
              </li>
              <li>
                ページ下部の「アプリケーションパスワード」欄で新規作成(名前: 「marketer」など)
              </li>
              <li>表示された 24 文字のパスワードをコピー(以後表示できないので注意)</li>
              <li>
                下のフォームに <b>サイト URL</b> / <b>ユーザー名</b> / <b>アプリパスワード</b> を入力
              </li>
            </ol>
          </div>
        </CardContent>
      </Card>

      {wp?.registered && (
        <Card>
          <CardContent className="flex items-center justify-between pt-6">
            <div>
              <div className="font-medium">登録済み</div>
              <div className="text-xs text-muted-foreground">
                パスワード: {wp.masked ?? '****'} / 更新:{' '}
                {wp.updated_at ? new Date(wp.updated_at).toLocaleString() : '—'}
              </div>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (confirm('WordPress 認証情報を削除しますか?')) remove.mutate();
              }}
            >
              削除
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{wp?.registered ? '更新する' : '新規登録'}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field
            label="WordPress サイト URL"
            required={!wp?.registered}
            hint="末尾スラッシュなし。例: https://kiseeeen.co.jp"
          >
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </Field>
          <Field label="WordPress ユーザー名" required={!wp?.registered} hint="管理画面のログイン ID">
            <Input value={userLogin} onChange={(e) => setUserLogin(e.target.value)} />
          </Field>
          <Field
            label="アプリケーションパスワード"
            required={!wp?.registered}
            hint="WP の「ユーザー → プロフィール」で生成した 24 文字のパスワード(空白あり)"
          >
            <Input
              type="password"
              value={appPassword}
              onChange={(e) => setAppPassword(e.target.value)}
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            onClick={() => upsert.mutate()}
            disabled={
              upsert.isPending ||
              (!baseUrl.trim() && !userLogin.trim() && !appPassword.trim())
            }
          >
            {wp?.registered ? '更新' : '保存'}
          </Button>
          <p className="text-xs text-muted-foreground">
            ※ パスワードは Fernet 暗号化で保管され、保存後は再表示されません(マスク表示のみ)。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
