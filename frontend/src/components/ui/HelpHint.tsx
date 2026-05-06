import { useEffect, useRef, useState } from 'react';

import { cn } from '@/lib/cn';

/**
 * 項目の意味と「何を見るべきか」を ? アイコンのクリックで表示するツールチップ。
 * - クリックで開閉(タッチデバイスでも使える)
 * - 外側クリック / Esc で閉じる
 * - title と body を分けて構造化テキストとして表示
 */
export function HelpHint({
  title,
  body,
  className,
}: {
  title?: string;
  body: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span
      ref={ref}
      className={cn('relative inline-flex align-middle', className)}
    >
      <button
        type="button"
        aria-label="この項目の説明"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={cn(
          'inline-flex h-4 w-4 items-center justify-center rounded-full',
          'border border-border bg-background text-[10px] font-bold text-muted-foreground',
          'hover:bg-muted hover:text-foreground transition-colors',
          open && 'bg-muted text-foreground',
        )}
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          className={cn(
            'absolute left-1/2 top-full z-50 mt-1.5 w-72 -translate-x-1/2',
            'rounded-md border border-border bg-card p-3 text-xs leading-relaxed',
            'text-card-foreground shadow-lg ring-1 ring-black/5 dark:ring-white/10',
          )}
        >
          {title && (
            <div className="mb-1.5 font-semibold text-foreground">{title}</div>
          )}
          <div className="space-y-1.5 text-muted-foreground">{body}</div>
        </span>
      )}
    </span>
  );
}
