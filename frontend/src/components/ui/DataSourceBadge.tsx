import { useEffect, useRef, useState } from 'react';

import type { DataSourceInfo } from '@/api/dashboard';
import { cn } from '@/lib/cn';

/**
 * 「データの新しさ」を 1 行で示すバッジ。
 * - 複数ソースを束ねて表示する場合は最も古い「最終取得日」をサマリ値として出す。
 * - クリックで各ソースのカバレッジ範囲・ジョブ最終成功時刻を詳細表示。
 */

function formatDate(s: string | null | undefined): string {
  if (!s) return '—';
  // YYYY-MM-DD のみ来る前提
  return s.slice(0, 10);
}

function formatDateTime(s: string | null | undefined): string {
  if (!s) return '—';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '—';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${y}-${m}-${day} ${hh}:${mm}`;
}

function relativeFromDate(s: string | null | undefined): string {
  if (!s) return '';
  const target = new Date(s);
  if (Number.isNaN(target.getTime())) return '';
  const now = new Date();
  const ms = now.getTime() - target.getTime();
  const days = Math.floor(ms / (24 * 3600 * 1000));
  if (days <= 0) return '今日';
  if (days === 1) return '1 日前';
  if (days < 7) return `${days} 日前`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks} 週間前`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} ヶ月前`;
  return `${Math.floor(days / 365)} 年前`;
}

function relativeFromTs(s: string | null | undefined): string {
  if (!s) return '';
  const target = new Date(s);
  if (Number.isNaN(target.getTime())) return '';
  const ms = Date.now() - target.getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return 'たった今';
  if (min < 60) return `${min} 分前`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} 時間前`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} 日前`;
  const w = Math.floor(d / 7);
  if (w < 5) return `${w} 週間前`;
  const mo = Math.floor(d / 30);
  if (mo < 12) return `${mo} ヶ月前`;
  return `${Math.floor(d / 365)} 年前`;
}

export function DataSourceBadge({
  sources,
  className,
}: {
  sources: DataSourceInfo[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
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

  // 利用可能なソースだけ。空(配列要素 0)なら何も表示しない。
  const visible = sources.filter(Boolean);
  if (visible.length === 0) return null;

  // サマリは「最も古い coverage_to」と「最も古い last_job_at」を採用 = 一番遅れているソースを基準。
  const oldestCoverage = visible
    .map((s) => s.coverage_to)
    .filter((v): v is string => !!v)
    .sort()[0];
  const oldestJobAt = visible
    .map((s) => s.last_job_at)
    .filter((v): v is string => !!v)
    .sort()[0];

  // 提供元のユニークセット(GA4 / GSC など)。
  const providers = Array.from(new Set(visible.map((s) => s.provider)));
  const summaryProvider = providers.join(' / ');

  const summary = oldestCoverage
    ? `${formatDate(oldestCoverage)}(${relativeFromDate(oldestCoverage)})`
    : oldestJobAt
      ? relativeFromTs(oldestJobAt)
      : 'データなし';

  return (
    <span ref={ref} className={cn('relative inline-flex align-middle', className)}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={cn(
          'inline-flex items-center gap-1 rounded border border-border bg-muted/40 px-1.5 py-0.5',
          'text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors',
          open && 'bg-muted text-foreground',
        )}
        aria-label="データソースの詳細"
        aria-expanded={open}
      >
        <span className="font-medium">{summaryProvider}</span>
        <span>·</span>
        <span>{summary}</span>
      </button>
      {open && (
        <span
          role="tooltip"
          className={cn(
            'absolute right-0 top-full z-50 mt-1.5 w-80',
            'rounded-md border border-border bg-card p-3 text-xs leading-relaxed',
            'text-card-foreground shadow-lg ring-1 ring-black/5 dark:ring-white/10',
          )}
        >
          <div className="mb-1.5 font-semibold text-foreground">データソース</div>
          <table className="w-full text-[11px]">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-0.5 pr-2">提供元</th>
                <th className="py-0.5 pr-2">名称</th>
                <th className="py-0.5 pr-2">最終</th>
                <th className="py-0.5 text-right">行数</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr key={s.key} className="border-t border-border">
                  <td className="py-0.5 pr-2">{s.provider}</td>
                  <td className="py-0.5 pr-2">{s.label}</td>
                  <td className="py-0.5 pr-2">
                    {formatDate(s.coverage_to)}
                    {s.coverage_from && (
                      <span className="ml-1 text-muted-foreground">
                        〜 {formatDate(s.coverage_from)} から
                      </span>
                    )}
                  </td>
                  <td className="py-0.5 text-right tabular-nums">
                    {s.row_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {oldestJobAt && (
            <div className="mt-2 text-[11px] text-muted-foreground">
              直近のジョブ成功: {formatDateTime(oldestJobAt)}({relativeFromTs(oldestJobAt)})
            </div>
          )}
        </span>
      )}
    </span>
  );
}
