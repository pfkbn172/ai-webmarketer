/**
 * 事業情報タブ。business_context を編集する画面。
 *
 * 自由記述から AI に JSON を組み立ててもらう「✨ AI に質問して埋めてもらう」
 * ボタンも提供する。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import {
  aiHearing,
  fetchBusinessContext,
  updateBusinessContext,
  type BusinessContext,
} from '@/api/business_context';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';

const STAGE_OPTIONS = [
  { value: 'solo', label: '一人法人 / 個人' },
  { value: 'micro', label: '零細(2〜5 名)' },
  { value: 'smb', label: '中小(6〜50 名)' },
  { value: 'enterprise', label: '中堅以上(50 名超)' },
];

const EMPTY: BusinessContext = {
  stage: null,
  geographic_base: [],
  geographic_expansion: [],
  unique_value: [],
  primary_offerings: [],
  target_customer: null,
  weak_segments: [],
  strong_segments: [],
  compliance_constraints: [],
};

const csv = (a: string[]) => a.join(', ');
const uncsv = (s: string) =>
  s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

export default function BusinessContextTab() {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ['business_context'],
    queryFn: fetchBusinessContext,
  });

  const [form, setForm] = useState<BusinessContext>(EMPTY);
  const [hearing, setHearing] = useState('');

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const update = useMutation({
    mutationFn: (v: BusinessContext) => updateBusinessContext(v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['business_context'] }),
  });
  const ai = useMutation({
    mutationFn: (text: string) => aiHearing(text),
    onSuccess: (v) => {
      setForm(v);
      setHearing('');
      qc.invalidateQueries({ queryKey: ['business_context'] });
    },
  });

  if (isPending) {
    return <p className="text-sm text-muted-foreground">読み込み中…</p>;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>事業情報</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            この情報は<b>戦略レビュー / クエリ提案 / 月次レポート</b>のすべてで AI が
            プロのマーケター視点で提言する判断材料として使われます。具体的に書くほど
            提言の質が上がります。
          </p>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>✨ AI に質問して埋めてもらう</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            自由記述で「自分の事業について話す」ように書いてください。AI が
            自動で下のフォームを構造化して埋めます。既に値が入っている項目は保持されます。
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            rows={6}
            value={hearing}
            onChange={(e) => setHearing(e.target.value)}
            placeholder="例: 大阪の天王寺区を拠点に、一人法人で IT/DX サポートをやっています。タイの三菱ガス化学グループで 10 年営業部長を経験し、製造業の経営課題に詳しいのが強みです。地域の中小企業の経営者をターゲットにしていて、業種特化ではなく地域密着で実績があります。"
          />
          <Button
            onClick={() => ai.mutate(hearing)}
            disabled={!hearing.trim() || ai.isPending}
          >
            {ai.isPending ? '解析中…' : 'AI に解析させて埋める'}
          </Button>
          {ai.isError && (
            <p className="text-sm text-destructive">
              AI 解析失敗: {(ai.error as any)?.response?.data?.detail ?? '不明'}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>事業基本情報</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field
            label="事業ステージ"
            hint="一人〜零細だと広域クエリで勝てないため、戦略を変える必要があります"
          >
            <Select
              value={form.stage ?? ''}
              onChange={(e) => setForm({ ...form, stage: e.target.value || null })}
            >
              <option value="">— 選択 —</option>
              {STAGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="拠点地域(現状勝てている地域)"
            hint="カンマ区切りで複数。例: 平野区, 天王寺区, 阿倍野区"
          >
            <Input
              value={csv(form.geographic_base)}
              onChange={(e) =>
                setForm({ ...form, geographic_base: uncsv(e.target.value) })
              }
            />
          </Field>

          <Field
            label="拡大目標地域"
            hint="まだ実績はないが、これから取りに行く地域"
          >
            <Input
              value={csv(form.geographic_expansion)}
              onChange={(e) =>
                setForm({ ...form, geographic_expansion: uncsv(e.target.value) })
              }
            />
          </Field>

          <Field
            label="独自性・強み"
            hint="他社にない経歴・スキル・実績。E-E-A-T のシグナルとして AI に渡される"
          >
            <Textarea
              rows={3}
              value={csv(form.unique_value)}
              onChange={(e) =>
                setForm({ ...form, unique_value: uncsv(e.target.value) })
              }
            />
          </Field>

          <Field
            label="主要サービス"
            hint="提供している中心サービス。クエリ生成の素材に使われる"
          >
            <Textarea
              rows={2}
              value={csv(form.primary_offerings)}
              onChange={(e) =>
                setForm({ ...form, primary_offerings: uncsv(e.target.value) })
              }
            />
          </Field>

          <Field label="ターゲット顧客" hint="自由記述">
            <Input
              value={form.target_customer ?? ''}
              onChange={(e) =>
                setForm({ ...form, target_customer: e.target.value || null })
              }
            />
          </Field>

          <Field
            label="弱点セグメント(避けるべき土俵)"
            hint="「業種特化では大手に勝てない」など。AI は提案でこの領域を避ける"
          >
            <Textarea
              rows={2}
              value={csv(form.weak_segments)}
              onChange={(e) =>
                setForm({ ...form, weak_segments: uncsv(e.target.value) })
              }
            />
          </Field>

          <Field
            label="強いセグメント(勝てる土俵)"
            hint="「地域 × IT/DX サポート」など、実証済の勝ちパターン"
          >
            <Textarea
              rows={2}
              value={csv(form.strong_segments)}
              onChange={(e) =>
                setForm({ ...form, strong_segments: uncsv(e.target.value) })
              }
            />
          </Field>

          <Button onClick={() => update.mutate(form)} disabled={update.isPending}>
            {update.isPending ? '保存中…' : '保存'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
