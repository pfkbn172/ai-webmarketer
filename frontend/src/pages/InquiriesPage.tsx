import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  createInquiry,
  listInquiries,
  updateInquiryStatus,
  type AiOrigin,
  type Inquiry,
  type InquirySourceChannel,
  type InquiryStatus,
} from '@/api/inquiries';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Input } from '@/components/ui/Input';

const SOURCE_LABELS: Record<InquirySourceChannel, string> = {
  web: 'Web フォーム',
  email: 'メール',
  phone: '電話',
  ai: 'AI チャット',
  other: 'その他',
};
const AI_LABELS: Record<AiOrigin, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  gemini: 'Gemini',
  aio: 'AI Overviews',
};
const STATUS_LABELS: Record<InquiryStatus, string> = {
  new: '新規',
  in_progress: '対応中',
  contracted: '契約',
  lost: '失注',
};

export default function InquiriesPage() {
  const qc = useQueryClient();
  const { data: inquiries = [] } = useQuery({
    queryKey: ['inquiries'],
    queryFn: listInquiries,
  });
  const [showForm, setShowForm] = useState(false);

  const create = useMutation({
    mutationFn: (payload: Partial<Inquiry>) => createInquiry(payload),
    onSuccess: () => {
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ['inquiries'] });
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: InquiryStatus }) =>
      updateInquiryStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inquiries'] }),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>問い合わせログ</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            問い合わせフォームから自動で受信した分(Webhook 経由)に加えて、
            電話・口頭・メールなど Web 以外で受けた問い合わせを手動で記録できます。
            「AI 起点」を選ぶと、ChatGPT 等の AI 検索経由でたどり着いた可能性を記録できます。
          </p>
        </CardHeader>
        <CardContent>
          <Button onClick={() => setShowForm((v) => !v)}>
            {showForm ? '閉じる' : '+ 手動で問い合わせを追加'}
          </Button>
        </CardContent>
      </Card>

      {showForm && <InquiryForm onSubmit={(p) => create.mutate(p)} />}

      <Card>
        <CardHeader>
          <CardTitle>登録済み({inquiries.length} 件)</CardTitle>
        </CardHeader>
        <CardContent>
          {inquiries.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              まだ問い合わせがありません
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-3">受信日時</th>
                    <th className="py-2 pr-3">経路</th>
                    <th className="py-2 pr-3">AI 起点</th>
                    <th className="py-2 pr-3">業種</th>
                    <th className="py-2 pr-3">内容</th>
                    <th className="py-2">ステータス</th>
                  </tr>
                </thead>
                <tbody>
                  {inquiries.map((i: Inquiry) => (
                    <tr key={i.id} className="border-b border-border/50 align-top">
                      <td className="py-2 pr-3 text-xs">
                        {i.received_at ? new Date(i.received_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-2 pr-3 text-xs">{SOURCE_LABELS[i.source_channel]}</td>
                      <td className="py-2 pr-3 text-xs">
                        {i.ai_origin ? AI_LABELS[i.ai_origin] : '—'}
                      </td>
                      <td className="py-2 pr-3 text-xs">{i.industry ?? '—'}</td>
                      <td className="py-2 pr-3 text-xs max-w-[300px] truncate">
                        {i.content_text}
                      </td>
                      <td className="py-2">
                        <Select
                          value={i.status}
                          onChange={(e) =>
                            updateStatus.mutate({
                              id: i.id,
                              status: e.target.value as InquiryStatus,
                            })
                          }
                          className="h-8 text-xs"
                        >
                          {(Object.keys(STATUS_LABELS) as InquiryStatus[]).map((s) => (
                            <option key={s} value={s}>
                              {STATUS_LABELS[s]}
                            </option>
                          ))}
                        </Select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function InquiryForm({ onSubmit }: { onSubmit: (p: Partial<Inquiry>) => void }) {
  const [content, setContent] = useState('');
  const [industry, setIndustry] = useState('');
  const [companySize, setCompanySize] = useState('');
  const [source, setSource] = useState<InquirySourceChannel>('phone');
  const [aiOrigin, setAiOrigin] = useState<AiOrigin | ''>('');

  return (
    <Card>
      <CardHeader>
        <CardTitle>問い合わせを手動入力</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field
          label="問い合わせ内容"
          required
          hint="電話メモや口頭で聞いた内容をそのまま貼り付けで OK"
        >
          <Textarea
            rows={4}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="例: 製造業向けの DX コンサルを探していて、ChatGPT で検索したところ御社のサイトを見つけた。月 1 回の打ち合わせから始められるか?"
          />
        </Field>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="業種" hint="例: 製造業 / 法律事務所">
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </Field>
          <Field label="企業規模" hint="例: 〜10 名 / 50〜100 名">
            <Input value={companySize} onChange={(e) => setCompanySize(e.target.value)} />
          </Field>
          <Field label="経路" required hint="どこから来た問い合わせか">
            <Select value={source} onChange={(e) => setSource(e.target.value as InquirySourceChannel)}>
              {(Object.keys(SOURCE_LABELS) as InquirySourceChannel[]).map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABELS[s]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field
          label="AI 起点"
          hint="お客様が「ChatGPT で検索して見つけた」と言った場合などに選択。不明なら空のまま。"
        >
          <Select value={aiOrigin} onChange={(e) => setAiOrigin(e.target.value as AiOrigin | '')}>
            <option value="">— 不明 / 選択しない —</option>
            {(Object.keys(AI_LABELS) as AiOrigin[]).map((a) => (
              <option key={a} value={a}>
                {AI_LABELS[a]}
              </option>
            ))}
          </Select>
        </Field>
        <Button
          disabled={!content.trim()}
          onClick={() =>
            onSubmit({
              content_text: content,
              industry: industry || null,
              company_size: companySize || null,
              source_channel: source,
              ai_origin: aiOrigin || null,
              status: 'new',
            })
          }
        >
          記録する
        </Button>
      </CardContent>
    </Card>
  );
}
