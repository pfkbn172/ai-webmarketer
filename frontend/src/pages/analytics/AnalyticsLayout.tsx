import SectionTabs from '@/components/layout/SectionTabs';

const TABS = [
  { to: '/analytics', label: '集客', startsWith: false },
  { to: '/analytics/citations', label: '引用率(LLM)' },
  { to: '/analytics/rank', label: '検索順位' },
  { to: '/analytics/quality', label: 'サイト品質' },
];

export default function AnalyticsLayout() {
  return (
    <SectionTabs
      title="📊 分析"
      description="集客 / LLM引用率 / 検索順位 / サイト品質を一画面で確認します。"
      tabs={TABS}
    />
  );
}
