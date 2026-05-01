import { Navigate, useLocation } from 'react-router-dom';

import { useMe } from '@/hooks/useAuth';

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { data: me, isPending, isError } = useMe();

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        読み込み中…
      </div>
    );
  }
  if (isError || !me) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
