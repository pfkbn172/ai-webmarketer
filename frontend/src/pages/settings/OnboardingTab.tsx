import { Link } from 'react-router-dom';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

/**
 * オンボーディング:6ステップで初回セットアップを案内する。
 * 各ステップの本体は既存タブ(/settings/business 等)に飛ばすだけで、
 * 進捗自体は localStorage で簡易管理する(管理サーバ側マスターは将来追加)。
 */

type Step = {
  index: number;
  title: string;
  description: string;
  target: string;
  storageKey: string;
};

const STEPS: Step[] = [
  {
    index: 1,
    title: '事業情報を入力',
    description:
      '名称・拠点・主要サービス・ターゲット顧客などをまず登録します。これがすべての AI 提案の根拠になります。',
    target: '/settings/business',
    storageKey: 'onboarding_step_1_business',
  },
  {
    index: 2,
    title: 'Google Search Console を連携',
    description: 'GSC OAuth でクエリ・順位データを取得します。',
    target: '/settings/credentials',
    storageKey: 'onboarding_step_2_gsc',
  },
  {
    index: 3,
    title: 'Google Analytics 4 を連携',
    description: 'GA4 OAuth でセッション・CV・参照元を取得します。',
    target: '/settings/credentials',
    storageKey: 'onboarding_step_3_ga4',
  },
  {
    index: 4,
    title: 'WordPress 連携を登録',
    description: 'App Password を発行して、ブリーフから WP 下書きを作れるようにします。',
    target: '/settings/credentials',
    storageKey: 'onboarding_step_4_wp',
  },
  {
    index: 5,
    title: '競合を 3 社以上登録',
    description: '見出し・タイトルから競合がカバーするキーワードを学習します。',
    target: '/settings/competitors',
    storageKey: 'onboarding_step_5_competitors',
  },
  {
    index: 6,
    title: 'AI Provider キーを設定',
    description: 'Gemini/Claude/OpenAI のキーをユースケース別に割当てます。',
    target: '/settings/credentials',
    storageKey: 'onboarding_step_6_ai',
  },
];

const isDone = (key: string): boolean =>
  typeof window !== 'undefined' && window.localStorage.getItem(key) === '1';

export default function OnboardingTab() {
  const total = STEPS.length;
  const done = STEPS.filter((s) => isDone(s.storageKey)).length;

  const toggle = (key: string) => {
    const cur = isDone(key);
    if (cur) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, '1');
    // 簡易リフレッシュ
    window.dispatchEvent(new Event('storage'));
    location.reload();
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">オンボーディング</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            初回セットアップの手順です。完了したらチェックを入れてください
            (この進捗はブラウザ側に保存されます。サーバー側の正解値ではないので、誤チェックも自由に外せます)。
          </p>
        </CardHeader>
        <CardContent>
          <div className="text-sm">
            進捗:&nbsp;
            <span className={done === total ? 'font-bold text-emerald-700' : 'font-bold'}>
              {done}/{total}
            </span>
            {done === total && '  🎉 セットアップ完了'}
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded bg-slate-200">
            <div
              className="h-2 bg-emerald-500"
              style={{ width: `${Math.round((done / total) * 100)}%` }}
            />
          </div>
        </CardContent>
      </Card>

      <ol className="space-y-3">
        {STEPS.map((s) => {
          const checked = isDone(s.storageKey);
          return (
            <li key={s.index}>
              <Card>
                <CardContent className="flex items-start gap-3 py-4">
                  <button
                    type="button"
                    aria-label="完了マーク切替"
                    onClick={() => toggle(s.storageKey)}
                    className={`mt-1 h-6 w-6 shrink-0 rounded border text-center text-sm ${
                      checked
                        ? 'border-emerald-500 bg-emerald-500 text-white'
                        : 'border-slate-300 bg-white'
                    }`}
                  >
                    {checked ? '✓' : ''}
                  </button>
                  <div className="flex-1">
                    <div className="font-semibold">
                      Step {s.index}: {s.title}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{s.description}</p>
                  </div>
                  <Link
                    to={s.target}
                    className="self-center rounded border px-3 py-1 text-xs hover:bg-slate-50"
                  >
                    開く →
                  </Link>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
