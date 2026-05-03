import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';
import ApiKeysTab from '@/pages/settings/ApiKeysTab';
import AuthorsTab from '@/pages/settings/AuthorsTab';
import BusinessContextTab from '@/pages/settings/BusinessContextTab';
import CompetitorsTab from '@/pages/settings/CompetitorsTab';
import WordPressTab from '@/pages/settings/WordPressTab';

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>設定</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            事業情報・著者プロフィール・競合・連携サービス・API キーをここで管理します。
            各タブには「初めての方向けの手順」も記載しています。
          </p>
        </CardHeader>
        <CardContent>
          <Tabs
            tabs={[
              { id: 'business', label: '事業情報 (戦略の根拠)', content: <BusinessContextTab /> },
              { id: 'authors', label: '著者プロフィール', content: <AuthorsTab /> },
              { id: 'competitors', label: '競合', content: <CompetitorsTab /> },
              { id: 'wordpress', label: 'WordPress 連携', content: <WordPressTab /> },
              { id: 'apikeys', label: 'API キー', content: <ApiKeysTab /> },
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}
