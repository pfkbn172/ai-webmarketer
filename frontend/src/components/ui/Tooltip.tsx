import { useState } from 'react';

import { cn } from '@/lib/cn';

/**
 * 軽量ホバーツールチップ。Radix 等を入れる前の最小実装。
 * children をマウスオーバーするだけで表示される。配置は children の真上(中央寄せ)。
 */
export function Tooltip({
  content,
  children,
  className,
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-50 shadow-lg"
        >
          {content}
        </span>
      )}
    </span>
  );
}
