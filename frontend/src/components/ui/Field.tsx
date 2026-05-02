import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

type Props = {
  label: string;
  htmlFor?: string;
  required?: boolean;
  hint?: ReactNode;
  error?: string | null;
  children: ReactNode;
  className?: string;
};

/** ラベル + 説明 + 入力欄 + エラーをまとめる初心者フレンドリな field。 */
export function Field({
  label,
  htmlFor,
  required,
  hint,
  error,
  children,
  className,
}: Props) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="flex items-center gap-1 text-sm font-medium">
        {label}
        {required && <span className="text-destructive" aria-label="必須">*</span>}
        {!required && (
          <span className="text-xs font-normal text-muted-foreground">(任意)</span>
        )}
      </label>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
