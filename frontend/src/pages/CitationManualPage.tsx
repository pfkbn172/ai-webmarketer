/**
 * 引用モニタ手入力ページ。
 *
 * API 契約していない LLM(ChatGPT/Claude/Perplexity/AIO 等)について、
 * ユーザーが Web 版で実際に検索 → 結果を貼り付けて記録する。
 * 自動で self_cited / competitor_cited を判定して citation_logs に保存。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  submitManualCitation,
  type LLMProvider,
  type ManualCitationResult,
} from '@/api/citation_manual';
import { listQueries, type TargetQuery } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';

const LLM_OPTIONS: { id: LLMProvider; label: string; openUrl: string; howTo: string }[] = [
  {
    id: 'chatgpt',
    label: 'ChatGPT',
    openUrl: 'https://chatgpt.com/',
    howTo: 'ChatGPT を開いて検索ボタンを ON にしたうえでクエリを入力 → 回答全文と参照 URL リストをコピー',
  },
  {
    id: 'claude',
    label: 'Claude',
    openUrl: 'https://claude.ai/',
    howTo: 'Claude を開いて Web search ツールを ON でクエリを入力 → 回答と引用 URL をコピー',
  },
  {
    id: 'perplexity',
    label: 'Perplexity',
    openUrl: 'https://www.perplexity.ai/',
    howTo: 'Perplexity でクエリを入力 → 回答と Sources(参照 URL)をコピー',
  },
  {
    id: 'gemini',
    label: 'Gemini(Web 版)',
    openUrl: 'https://gemini.google.com/',
    howTo: 'Gemini を開いてクエリを入力 → 回答と引用 URL をコピー(API より制限が緩いことがある)',
  },
  {
    id: 'aio',
    label: 'Google AI Overviews',
    openUrl: 'https://www.google.com/',
    howTo: 'Google で検索 → 検索結果上部に「AI による概要」が表示されたらその文章と参照 URL をコピー',
  },
];

export default function CitationManualPage() {
  const qc = useQueryClient();
  const { data: queries = [] } = useQuery({
    queryKey: ['target_queries'],
    queryFn: listQueries,
  });

  const [queryId, setQueryId] = useState('');
  const [provider, setProvider] = useState<LLMProvider>('chatgpt');
  const [responseText, setResponseText] = useState('');
  const [urlsText, setUrlsText] = useState('');
  const [result, setResult] = useState<ManualCitationResult | null>(null);

  const selected = LLM_OPTIONS.find((o) => o.id === provider)!;
  const selectedQuery = queries.find((q: TargetQuery) => q.id === queryId);

  const submit = useMutation({
    mutationFn: () =>
      submitManualCitation({
        query_id: queryId,
        llm_provider: provider,
        response_text: responseText,
        cited_urls: urlsText
          .split(/\r?\n/)
          .map((u) => u.trim())
          .filter(Boolean),
      }),
    onSuccess: (res) => {
      setResult(res);
      setResponseText('');
      setUrlsText('');
      qc.invalidateQueries({ queryKey: ['citations'] });
    },
  });

  const canSubmit = queryId && responseText.trim().length > 0 && !submit.isPending;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>引用モニタ 手入力</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            API 契約していない LLM の引用結果を、Web 版で実際に検索して手で記録するページ。
            保存すると自動で「自社が引用されたか」を判定し、ダッシュボードと
            <b>「AI 引用モニタ」</b>画面に反映されます。
          </p>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-1 pl-6 text-sm text-muted-foreground">
            <li>下のクエリと LLM を選ぶ</li>
            <li>「LLM を開く」ボタンで対象サービスを別タブで開く</li>
            <li>そのクエリで検索して、回答全文と参照 URL リストをコピー</li>
            <li>このページに貼り付けて保存</li>
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="ターゲットクエリ"
              required
              hint="既に登録されているクエリから選択。未登録なら「ターゲットクエリ」画面で追加してください"
            >
              <Select value={queryId} onChange={(e) => setQueryId(e.target.value)}>
                <option value="">— 選択してください —</option>
                {queries.map((q: TargetQuery) => (
                  <option key={q.id} value={q.id}>
                    {q.query_text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="LLM" required hint="どの AI で検索した結果か">
              <Select value={provider} onChange={(e) => setProvider(e.target.value as LLMProvider)}>
                {LLM_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <div className="rounded-md border border-border bg-muted p-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="font-medium">{selected.label} の手順</div>
                <p className="mt-1 text-xs text-muted-foreground">{selected.howTo}</p>
                {selectedQuery && (
                  <p className="mt-2 text-xs">
                    検索クエリ: <code className="rounded bg-background px-2 py-0.5">{selectedQuery.query_text}</code>
                  </p>
                )}
              </div>
              <a
                href={selected.openUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
              >
                {selected.label} を開く ↗
              </a>
            </div>
          </div>

          <Field
            label="回答テキスト"
            required
            hint="LLM が返した回答全文を貼り付けてください(数千文字まで OK)"
          >
            <Textarea
              rows={10}
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder="例: AIウェブマーケターは、中小企業向けに SEO/LLMO の運用を自動化するシステムです..."
            />
          </Field>

          <Field
            label="参照 URL リスト"
            hint="1 行 1 URL で貼り付け。LLM が「Sources」「参考文献」として表示した URL"
          >
            <Textarea
              rows={5}
              value={urlsText}
              onChange={(e) => setUrlsText(e.target.value)}
              placeholder={'https://example.com/page1\nhttps://example.com/page2'}
            />
          </Field>

          <Button onClick={() => submit.mutate()} disabled={!canSubmit}>
            {submit.isPending ? '保存中…' : '記録する'}
          </Button>
          {submit.isError && (
            <p className="text-sm text-destructive">
              保存に失敗しました: {(submit.error as any)?.response?.data?.detail ?? '不明なエラー'}
            </p>
          )}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>記録完了</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              判定:{' '}
              {result.self_cited ? (
                <span className="font-semibold text-foreground">✓ 自社引用あり</span>
              ) : (
                <span className="text-destructive">✗ 自社引用なし</span>
              )}
            </div>
            {result.self_match_reason && (
              <div className="text-xs text-muted-foreground">
                判定根拠: {result.self_match_reason}
              </div>
            )}
            {result.competitor_cited.length > 0 && (
              <div>
                <div className="text-xs text-muted-foreground">競合引用:</div>
                <ul className="ml-4 list-disc text-xs">
                  {result.competitor_cited.map((c) => (
                    <li key={c.domain}>
                      {c.domain}: {c.count} 回
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
