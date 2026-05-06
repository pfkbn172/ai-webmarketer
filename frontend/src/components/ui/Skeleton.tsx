import { cn } from '@/lib/cn';

/**
 * 同寸の灰色ブロック + 揺らぎアニメーションでローディングを示す。
 * Tailwind の animate-pulse を利用。
 */
export function Skeleton({
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded bg-slate-200', className)}
      {...rest}
    />
  );
}

/** テーブル行ふうのスケルトン。rows 行 × cols 列の同寸プレースホルダ。 */
export function TableSkeleton({ rows = 6, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full">
      <div className="space-y-2 p-4">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-2">
            {Array.from({ length: cols }).map((_, j) => (
              <Skeleton
                key={j}
                className="h-4 flex-1"
                style={{ flexGrow: j === 0 ? 3 : 1 }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** カードレイアウト用のスケルトン。 */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-5 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </div>
  );
}
