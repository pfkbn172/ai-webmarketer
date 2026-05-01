import { Outlet, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { useLogout, useMe } from '@/hooks/useAuth';

export default function AppShell() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="font-semibold tracking-tight">AIウェブマーケター</div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          {me && <span>{me.email}</span>}
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
