import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export default function DashboardPage() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>AI 引用回数</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-semibold">—</div>
          <p className="mt-1 text-xs text-muted-foreground">W4-01 で実装</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>AI 引用率</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-semibold">—</div>
          <p className="mt-1 text-xs text-muted-foreground">W4-01 で実装</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>オーガニックセッション</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-semibold">—</div>
          <p className="mt-1 text-xs text-muted-foreground">W4-01 で実装</p>
        </CardContent>
      </Card>
    </div>
  );
}
