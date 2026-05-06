import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

/**
 * 検索順位タブ(Phase D で本格実装予定)。
 *
 * 当面は GSC の順位データが「集客」タブの DashboardPage に既に表示されているため、
 * ここではユーザーへの案内のみ表示。
 */
export default function RankPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">検索順位</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>
          Search Console から取得した検索順位の専用ビューは Phase D で実装予定です。
        </p>
        <p>
          現状、順位データは
          <a className="text-primary underline ml-1 mr-1" href="/marketer/analytics">
            集客タブ
          </a>
          のクエリ別パネルで確認できます。
        </p>
      </CardContent>
    </Card>
  );
}
