import { apiClient } from '@/api/client';

export type ClusterCitation = {
  cluster_id: string;
  total: number;
  self_cited: number;
  rate: number;
};

export type TopQueryRow = {
  query_text: string;
  clicks: number;
  impressions: number;
  ctr: number | null;
  avg_position: number | null;
};

export type HeatmapCell = { llm_provider: string; self_cited: number; total: number };
export type HeatmapRow = {
  query_text: string;
  cluster_id: string | null;
  cells: HeatmapCell[];
};

export type ChannelBreakdown = { channel: string; sessions: number };

export type NextAction = {
  id: string;
  text: string;
  rationale: string | null;
  completed: boolean;
};

export type Objective = {
  key: string;
  label: string;
  target: number;
  current: number;
  progress_pct: number;
};

export type CompetitorPatternMini = { domain: string; count: number; label: string };

export type AiReferralRow = { label: string; source_host: string; sessions: number };

export type PagePerformanceRow = {
  page_path: string;
  title: string | null;
  sessions: number;
  clicks: number;
  impressions: number;
  avg_position: number | null;
  citation_count: number;
};

export type FunnelStage = { status: string; count: number; amount_yen: number };
export type Funnel = {
  period_days: number;
  stages: FunnelStage[];
  cv_rate: number | null;
  avg_amount_yen: number | null;
  cpa_yen: number | null;
};

export type KeywordOpportunity = {
  query_text: string;
  impressions: number;
  avg_position: number | null;
  citation_rate: number;
  cluster_id: string | null;
  recommended_action: 'win' | 'optimize' | 'create' | 'monitor';
};

export type CompetitorContent = {
  domain: string;
  url: string;
  cite_count: number;
  sample_query: string | null;
};

export type AlertRule = {
  id: string;
  metric: 'sessions_drop_pct' | 'citations_drop_pct' | 'inquiries_zero_days' | 'anomaly';
  threshold: number;
  notify_email: string | null;
  notify_slack_webhook: string | null;
  enabled: boolean;
};

export async function fetchClusterCitation(days = 30): Promise<ClusterCitation[]> {
  return (
    await apiClient.get<ClusterCitation[]>('/dashboard/cluster-citation', {
      params: { days },
    })
  ).data;
}
export async function fetchTopQueries(days = 30, limit = 10): Promise<TopQueryRow[]> {
  return (
    await apiClient.get<TopQueryRow[]>('/dashboard/top-queries', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchHeatmap(days = 28, limit = 5): Promise<HeatmapRow[]> {
  return (
    await apiClient.get<HeatmapRow[]>('/dashboard/citation-heatmap', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchChannelBreakdown(days = 30): Promise<ChannelBreakdown[]> {
  return (
    await apiClient.get<ChannelBreakdown[]>('/dashboard/channel-breakdown', {
      params: { days },
    })
  ).data;
}
export async function fetchNextActions(): Promise<NextAction[]> {
  return (await apiClient.get<NextAction[]>('/dashboard/next-actions')).data;
}
export async function replaceNextActions(items: NextAction[]): Promise<NextAction[]> {
  return (await apiClient.put<NextAction[]>('/dashboard/next-actions', { items })).data;
}
export async function generateNextActionsWithAi(): Promise<NextAction[]> {
  return (await apiClient.post<NextAction[]>('/dashboard/next-actions/from-ai')).data;
}
export async function fetchObjectives(): Promise<Objective[]> {
  return (await apiClient.get<Objective[]>('/dashboard/objectives')).data;
}
export async function upsertObjectives(payload: {
  monthly_sessions?: number;
  monthly_citations?: number;
  monthly_inquiries?: number;
  monthly_contents?: number;
}): Promise<Objective[]> {
  return (await apiClient.put<Objective[]>('/dashboard/objectives', payload)).data;
}
export async function fetchCompetitorPatternsTop(
  days = 30,
): Promise<CompetitorPatternMini[]> {
  return (
    await apiClient.get<CompetitorPatternMini[]>('/dashboard/competitor-patterns-top', {
      params: { days },
    })
  ).data;
}
export async function fetchAiReferrals(days = 30): Promise<AiReferralRow[]> {
  return (
    await apiClient.get<AiReferralRow[]>('/dashboard/ai-referrals', { params: { days } })
  ).data;
}
export async function fetchPagePerformance(
  days = 30,
  limit = 20,
): Promise<PagePerformanceRow[]> {
  return (
    await apiClient.get<PagePerformanceRow[]>('/dashboard/page-performance', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchFunnel(days = 90): Promise<Funnel> {
  return (await apiClient.get<Funnel>('/dashboard/funnel', { params: { days } })).data;
}
export async function fetchKeywordOpportunity(
  days = 30,
  limit = 30,
): Promise<KeywordOpportunity[]> {
  return (
    await apiClient.get<KeywordOpportunity[]>('/dashboard/keyword-opportunity', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchCompetitorContent(
  days = 30,
  limit = 20,
): Promise<CompetitorContent[]> {
  return (
    await apiClient.get<CompetitorContent[]>('/dashboard/competitor-content', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchAlertRules(): Promise<AlertRule[]> {
  return (await apiClient.get<AlertRule[]>('/dashboard/alert-rules')).data;
}
export async function replaceAlertRules(items: AlertRule[]): Promise<AlertRule[]> {
  return (await apiClient.put<AlertRule[]>('/dashboard/alert-rules', { items })).data;
}
