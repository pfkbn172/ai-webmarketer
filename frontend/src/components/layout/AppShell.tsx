import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { useLogout, useMe } from '@/hooks/useAuth';
import { cn } from '@/lib/cn';

/**
 * 5タブ集約ナビ。
 * - exact: true は完全一致のみ active(ホーム用)
 * - それ以外は `to` プレフィックスで始まるパスを全部 active 扱い(子ページでも親タブが光る)
 * - 旧URL(/strategic /queries /keyword-universe ...)へのアクセスは App.tsx の Navigate で
 *   新URL にリダイレクトされる前提なので、ここでは新URLだけ並べる。
 */
const NAV = [
  { to: '/', label: '🏠 ホーム', exact: true },
  { to: '/analytics', label: '📊 分析' },
  { to: '/strategy', label: '🎯 戦略' },
  { to: '/production', label: '✏️ 制作' },
  { to: '/settings', label: '⚙️ 設定' },
];

export default function AppShell() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (item: (typeof NAV)[number]) => {
    if (item.exact) return location.pathname === item.to;
    return (
      location.pathname === item.to ||
      location.pathname.startsWith(item.to + '/')
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <Link to="/" className="font-semibold tracking-tight">
          AIウェブマーケター
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm transition-colors',
                isActive(n)
                  ? 'bg-secondary text-secondary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          {me && <span className="hidden sm:inline">{me.email}</span>}
          <Button
            size="sm"
            variant="ghost"
            onClick={async () => {
              await logout.mutateAsync();
              navigate('/login', { replace: true });
            }}
          >
            ログアウト
          </Button>
        </div>
      </header>
      <main className="container py-6">
        <Outlet />
      </main>
    </div>
  );
}
