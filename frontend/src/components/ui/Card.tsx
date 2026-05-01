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

export function CardContent({
  className,
  children,
}: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('p-6 pt-2', className)}>{children}</div>;
}
