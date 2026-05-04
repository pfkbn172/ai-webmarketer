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

export async function fetchClusterCitation(): Promise<ClusterCitation[]> {
  return (await apiClient.get<ClusterCitation[]>('/dashboard/cluster-citation')).data;
}
export async function fetchTopQueries(limit = 10): Promise<TopQueryRow[]> {
  return (await apiClient.get<TopQueryRow[]>('/dashboard/top-queries', { params: { limit } }))
    .data;
}
export async function fetchHeatmap(limit = 5): Promise<HeatmapRow[]> {
  return (await apiClient.get<HeatmapRow[]>('/dashboard/citation-heatmap', { params: { limit } }))
    .data;
}
export async function fetchChannelBreakdown(): Promise<ChannelBreakdown[]> {
  return (await apiClient.get<ChannelBreakdown[]>('/dashboard/channel-breakdown')).data;
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
export async function fetchCompetitorPatternsTop(): Promise<CompetitorPatternMini[]> {
  return (
    await apiClient.get<CompetitorPatternMini[]>('/dashboard/competitor-patterns-top')
  ).data;
}
