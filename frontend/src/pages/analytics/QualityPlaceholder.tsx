import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

/**
 * サイト品質タブ(Phase D で本格実装予定)。
 *
 * PageSpeed の Core Web Vitals は既に「集客」タブのダッシュボードに表示済み。
 * 構造化データ適用状況・schema_audit_logs の集約はここに移植予定。
 */
export default function QualityPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">サイト品質</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>Core Web Vitals / 構造化データ / インデックス状況の専用ビューは Phase D で実装予定です。</p>
        <p>
          現状、Core Web Vitals は
          <a className="text-primary underline ml-1 mr-1" href="/marketer/analytics">
            集客タブ
          </a>
          のサイト健全性パネルで確認できます。
        </p>
      </CardContent>
    </Card>
  );
}
