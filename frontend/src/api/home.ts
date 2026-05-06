import { apiClient } from '@/api/client';

export type Severity = 'red' | 'yellow' | 'green';

export type TodayAction = {
  id: string;
  action_index: number;
  severity: Severity;
  title: string;
  rationale: string | null;
  target_url: string | null;
  related_keyword: string | null;
  generated_at: string;
};

export type KpiSummary = {
  ai_referral_sessions_7d: number;
  ai_referral_sessions_prev_7d: number;
  self_cite_rate_30d: number | null;
  inquiries_30d: number;
  opportunity_count: number;
};

export type HealthIssue = {
  job_name: string;
  severity: 'warning' | 'error';
  message: string;
  target_url: string | null;
};

export type RecentUpdate = {
  kind: 'brief' | 'aggregate' | 'job';
  title: string;
  when: string;
  target_url: string | null;
};

export type HomeToday = {
  actions: TodayAction[];
  kpi: KpiSummary;
  health: HealthIssue[];
  recent_updates: RecentUpdate[];
  actions_generated_at: string | null;
  actions_stale: boolean;
};

export async function getHomeToday(): Promise<HomeToday> {
  const res = await apiClient.get<HomeToday>('/home/today');
  return res.data;
}

export async function regenerateToday(): Promise<{ count: number }> {
  const res = await apiClient.post<{ count: number }>('/home/today/regenerate');
  return res.data;
}
