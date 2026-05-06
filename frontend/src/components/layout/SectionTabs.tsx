import { Link, Outlet, useLocation } from 'react-router-dom';

import { cn } from '@/lib/cn';

export type SectionTab = {
  to: string;
  label: string;
  /** /foo/bar で始まる場合に active 扱い。default: true。 */
  startsWith?: boolean;
};

/**
 * セクション配下のサブタブナビ + Outlet を備えた共通レイアウト。
 *
 * Phase C で /analytics, /strategy, /production, /settings の各セクションに
 * 共通のタブナビを被せるために使う。
 *
 * 詳細ページ(例: /production/briefs/:id)など、サブタブを出すと冗長になる場合は
 * `hideTabsWhen` に pathname を受け取って判定する関数を渡せば、そのページではタブを隠す。
 */
export default function SectionTabs({
  title,
  description,
  tabs,
  hideTabsWhen,
}: {
  title: string;
  description?: string;
  tabs: SectionTab[];
  hideTabsWhen?: (pathname: string) => boolean;
}) {
  const { pathname } = useLocation();
  const hideTabs = hideTabsWhen ? hideTabsWhen(pathname) : false;

  const isActive = (t: SectionTab) => {
    if (t.startsWith === false) return pathname === t.to;
    return pathname === t.to || pathname.startsWith(t.to + '/');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>

      {!hideTabs && (
        <nav className="flex flex-wrap gap-1 border-b border-border">
          {tabs.map((t) => (
            <Link
              key={t.to}
              to={t.to}
              className={cn(
                '-mb-px border-b-2 px-3 py-2 text-sm transition-colors',
                isActive(t)
                  ? 'border-foreground text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
      )}

      <Outlet />
    </div>
  );
}
