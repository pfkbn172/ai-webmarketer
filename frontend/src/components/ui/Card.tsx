import type { HTMLAttributes, PropsWithChildren } from 'react';

import { cn } from '@/lib/cn';

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card text-card-foreground shadow-sm',
        className,
      )}
      {...rest}
    />
  );
}

export function CardHeader({
  className,
  children,
}: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('p-6 pb-2', className)}>{children}</div>;
}

export function CardTitle({
  className,
  children,
}: PropsWithChildren<{ className?: string }>) {
  return (
    <h2 className={cn('text-xl font-semibold tracking-tight', className)}>{children}</h2>
  );
}

/**
 * カード見出し+ヘルプアイコンを 1 行に並べる構造ラッパー。
 * 見出し文字列の右に help 要素(?アイコン等)を並べ、ベースライン揃えを統一する。
 */
export function CardTitleWithHelp({
  className,
  children,
  help,
}: PropsWithChildren<{ className?: string; help?: React.ReactNode }>) {
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <h2 className={cn('text-xl font-semibold tracking-tight', className)}>{children}</h2>
      {help}
    </div>
  );
}

export function CardContent({
  className,
  children,
}: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('p-6 pt-2', className)}>{children}</div>;
}
