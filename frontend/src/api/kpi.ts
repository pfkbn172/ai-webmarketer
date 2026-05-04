import { apiClient } from '@/api/client';

export type KpiPoint = {
  date: string;
  sessions: number | null;
  ai_citation_count: number | null;
  inquiries_count: number | null;
};

export type KpiMetric = {
  value: number;
  prev_period_value: number;
  delta_pct: number | null;
};

export type KpiSummary = {
  period_days: number;
  ai_citation_count: number;
  sessions: number;
  inquiries_count: number;
  contents_published: number;
  series: KpiPoint[];
  metrics: Record<string, KpiMetric>;
};

export async function fetchKpiSummary(days = 30): Promise<KpiSummary> {
  const res = await apiClient.get<KpiSummary>(`/kpi/summary`, { params: { days } });
  return res.data;
}
