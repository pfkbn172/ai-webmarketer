import { apiClient } from '@/api/client';

export type KpiPoint = {
  date: string;
  sessions: number | null;
  ai_citation_count: number | null;
  inquiries_count: number | null;
  sessions_ma7: number | null;
  is_anomaly: boolean;
};

export type KpiMetric = {
  value: number;
  prev_period_value: number;
  delta_pct: number | null;
  prev_year_value: number | null;
  yoy_pct: number | null;
};

export type DataCoverage = {
  sessions_since: string | null;
  citations_since: string | null;
  inquiries_since: string | null;
  contents_since: string | null;
};

export type KpiSummary = {
  period_days: number;
  granularity: 'day' | 'week' | 'month';
  ai_citation_count: number;
  sessions: number;
  inquiries_count: number;
  contents_published: number;
  series: KpiPoint[];
  metrics: Record<string, KpiMetric>;
  coverage: DataCoverage;
};

export async function fetchKpiSummary(
  args: { days?: number; startDate?: string } = {},
): Promise<KpiSummary> {
  const params: Record<string, string | number> = {};
  if (args.startDate) params.start_date = args.startDate;
  else params.days = args.days ?? 30;
  const res = await apiClient.get<KpiSummary>(`/kpi/summary`, { params });
  return res.data;
}
