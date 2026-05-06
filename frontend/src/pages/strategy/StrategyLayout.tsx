import SectionTabs from '@/components/layout/SectionTabs';

const TABS = [
  { to: '/strategy/summary', label: '戦略サマリー' },
  { to: '/strategy/universe', label: 'キーワードユニバース' },
  { to: '/strategy/queries', label: 'クエリ管理' },
];

export default function StrategyLayout() {
  return (
    <SectionTabs
      title="🎯 戦略"
      description="AI戦略レビュー / データ駆動キーワード / 引用モニタ対象クエリ管理。"
      tabs={TABS}
    />
  );
}
