import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  deleteCredential,
  listCredentials,
  upsertCredential,
  type CredentialStatus,
} from '@/api/credentials';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';

type ApiKeyProvider = {
  id: string;
  label: string;
  description: string;
  obtainUrl: string;
  obtainHint: string;
};

const PROVIDERS: ApiKeyProvider[] = [
  {
    id: 'gemini_ai_engine',
    label: 'Gemini(AI 処理用)',
    description: '月次レポート生成・テーマ提案・記事ドラフトに使う。Phase 1 デフォルト。',
    obtainUrl: 'https://aistudio.google.com/apikey',
    obtainHint: 'Google AI Studio → 「Create API key」。AIzaSy で始まるキー。',
  },
  {
    id: 'gemini_citation_monitor',
    label: 'Gemini(引用モニタ用)',
    description:
      '週次の引用モニタで使う。AI 処理用と別 Google アカウントの API キーを使うと無料枠が 2 倍になります。',
    obtainUrl: 'https://aistudio.google.com/apikey',
    obtainHint: '別の Google アカウントでログインして同じ手順で発行。',
  },
  {
    id: 'openai',
    label: 'OpenAI(ChatGPT)',
    description: 'ChatGPT の引用モニタに使う。最低 $5 のクレジット入金が必要。',
    obtainUrl: 'https://platform.openai.com/api-keys',
    obtainHint: 'sk-proj- で始まるキー。Organization → Billing で課金設定も済ませる。',
  },
  {
    id: 'anthropic',
    label: 'Anthropic(Claude)',
    description: 'Claude の引用モニタに使う。最低 $5 のクレジット購入が必要。',
    obtainUrl: 'https://console.anthropic.com/settings/keys',
    obtainHint: 'sk-ant-api03- で始まるキー。Settings → Billing でクレジット購入。',
  },
  {
    id: 'perplexity',
    label: 'Perplexity',
    description: 'Perplexity の引用モニタに使う。最低 $5 のクレジット購入が必要。',
    obtainUrl: 'https://www.perplexity.ai/settings/api',
    obtainHint: 'pplx- で始まるキー。',
  },
  {
    id: 'serpapi',
    label: 'SerpApi(AI Overviews)',
    description:
      'Google AI Overviews の引用取得に使う。Developer プラン $75/月〜。Phase 1 では未契約なら AIO 列はスキップ。',
    obtainUrl: 'https://serpapi.com/users/sign_up',
    obtainHint: '料金が高いため、まずは Gemini + ChatGPT/Claude/Perplexity の運用で十分。',
  },
  {
    id: 'resend',
    label: 'Resend(メール送信)',
    description: '月次レポート・週次サマリ・異常検知メールの送信に使う。',
    obtainUrl: 'https://resend.com/api-keys',
    obtainHint: 're_ で始まるキー。事前にドメイン認証(SPF/DKIM)を済ませる。',
  },
];

function ProviderCard({
  provider,
  status,
  onSave,
  onDelete,
}: {
  provider: ApiKeyProvider;
  status: CredentialStatus | undefined;
  onSave: (key: string) => void;
  onDelete: () => void;
}) {
  const [val, setVal] = useState('');
  const registered = status?.registered ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {provider.label}
          {registered && (
            <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
              登録済み
            </span>
          )}
        </CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">{provider.description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {registered && (
          <div className="text-xs text-muted-foreground">
            現在のキー: {status?.masked ?? '****'}
          </div>
        )}
        <Field
          label="API キー"
          hint={
            <>
              <a
                href={provider.obtainUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                取得ページを開く →
              </a>
              <span className="ml-2">{provider.obtainHint}</span>
            </>
          }
        >
          <Input
            type="password"
            value={val}
            placeholder={registered ? '上書きする場合のみ入力' : 'API キーを貼り付け'}
            onChange={(e) => setVal(e.target.value)}
          />
        </Field>
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={!val.trim()}
            onClick={() => {
              onSave(val);
              setVal('');
            }}
          >
            {registered ? '更新' : '保存'}
          </Button>
          {registered && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (confirm(`${provider.label} のキーを削除しますか?`)) onDelete();
              }}
            >
              削除
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ApiKeysTab() {
  const qc = useQueryClient();
  const { data: creds = [] } = useQuery({
    queryKey: ['credentials'],
    queryFn: listCredentials,
  });

  const upsert = useMutation({
    mutationFn: ({ id, key }: { id: string; key: string }) =>
      upsertCredential(id, { api_key: key }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteCredential(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>AI Provider / 外部 API キー</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            各 AI プロバイダの API キーを登録します。キーは Fernet 暗号化で保管され、
            保存後は<b>マスク表示のみ</b>(平文では再表示されません)。
            キー取得は各サービスのリンクから無料・最低額で可能です。
          </p>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {PROVIDERS.map((p) => {
          const status = creds.find((c: CredentialStatus) => c.provider === p.id);
          return (
            <ProviderCard
              key={p.id}
              provider={p}
              status={status}
              onSave={(key) => upsert.mutate({ id: p.id, key })}
              onDelete={() => remove.mutate(p.id)}
            />
          );
        })}
      </div>
    </div>
  );
}
