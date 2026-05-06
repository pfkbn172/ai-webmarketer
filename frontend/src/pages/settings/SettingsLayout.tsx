import SectionTabs from '@/components/layout/SectionTabs';

const TABS = [
  { to: '/settings/business', label: '事業情報' },
  { to: '/settings/credentials', label: '認証情報' },
  { to: '/settings/competitors', label: '競合' },
  { to: '/settings/authors', label: '著者' },
  { to: '/settings/status', label: 'システム状態' },
  { to: '/settings/manual', label: 'マニュアル' },
  { to: '/settings/onboarding', label: 'オンボーディング' },
];

export default function SettingsLayout() {
  return (
    <SectionTabs
      title="⚙️ 設定"
      description="事業情報 / 各種認証 / 競合 / 著者 / システム状態 / マニュアル を一画面で管理。"
      tabs={TABS}
    />
  );
}
