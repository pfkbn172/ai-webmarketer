import SectionTabs from '@/components/layout/SectionTabs';

const TABS = [
  { to: '/production/briefs', label: 'ブリーフ' },
  { to: '/production/inquiries', label: '問い合わせ' },
];

// /production/briefs/<uuid> のときはタブを隠す(詳細表示が主役)。
// /production/briefs(末尾なし) は一覧なのでタブを出す。
const BRIEF_DETAIL_RE = /^\/production\/briefs\/[^/]+$/;

export default function ProductionLayout() {
  return (
    <SectionTabs
      title="✏️ 制作"
      description="AI生成されたコンテンツブリーフから WordPress 下書きまでを管理。"
      tabs={TABS}
      hideTabsWhen={(p) => BRIEF_DETAIL_RE.test(p)}
    />
  );
}
