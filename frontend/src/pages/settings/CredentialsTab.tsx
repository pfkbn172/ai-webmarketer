import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import ApiKeysTab from '@/pages/settings/ApiKeysTab';
import WordPressTab from '@/pages/settings/WordPressTab';

/**
 * 「認証情報」タブ — API キー(LLM/外部サービス)と WordPress 連携を1画面に集約。
 * GSC/GA4 の OAuth は今は別UI(将来オンボーディング側に移植予定)。
 */
export default function CredentialsTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">外部サービス連携</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            LLM Provider・PSI・Resend などの API キーと、WordPress 投稿連携をここで管理します。
          </p>
        </CardHeader>
        <CardContent>
          <ApiKeysTab />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">WordPress 連携</CardTitle>
        </CardHeader>
        <CardContent>
          <WordPressTab />
        </CardContent>
      </Card>
    </div>
  );
}
