import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { useLogout, useMe } from '@/hooks/useAuth';
import { cn } from '@/lib/cn';

const NAV = [
  { to: '/', label: 'ダッシュボード', exact: true },
  { to: '/strategic', label: '戦略レビュー' },
  { to: '/queries', label: 'クエリ' },
  { to: '/citations', label: '引用モニタ' },
  { to: '/citations/manual', label: '手入力' },
  { to: '/inquiries', label: '問い合わせ' },
  { to: '/settings', label: '設定' },
  { to: '/manual', label: 'マニュアル' },
];

export default function AppShell() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <Link to="/" className="font-semibold tracking-tight">
          AIウェブマーケター
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.exact}
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-1.5 text-sm transition-colors',
                  isActive
                    ? 'bg-secondary text-secondary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )
              }
            >
              {n.label}
            </NavLink>
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
