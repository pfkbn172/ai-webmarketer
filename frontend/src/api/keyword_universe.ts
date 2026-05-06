import { apiClient } from '@/api/client';

export type OpportunityFlag =
  | 'high_demand_no_coverage'
  | 'near_top_3'
  | 'low_demand'
  | null;

export type KeywordUniverseRow = {
  id: string;
  keyword: string;
  cluster_ids: string[];
  intent: string | null;
  is_geographic: boolean;
  gsc_imp_12m: number;
  gsc_clicks_12m: number;
  gsc_avg_position: number | null;
  suggest_derivative_count: number;
  competitor_coverage_count: number;
  llm_self_cite_rate: number | null;
  llm_competitor_cite_rate: number | null;
  priority_score: number;
  opportunity_flag: OpportunityFlag;
  source_breakdown: Record<string, unknown>;
};

export type ClusterCount = {
  cluster_id: string;
  rows: number;
};

export type KeywordUniverseFilter = {
  cluster_id?: string | null;
  min_priority?: number;
  opportunity_flag?: OpportunityFlag;
  limit?: number;
};

export async function listKeywordUniverse(
  filter: KeywordUniverseFilter = {},
): Promise<KeywordUniverseRow[]> {
  const params = new URLSearchParams();
  if (filter.cluster_id) params.set('cluster_id', filter.cluster_id);
  if (filter.min_priority !== undefined) params.set('min_priority', String(filter.min_priority));
  if (filter.opportunity_flag) params.set('opportunity_flag', filter.opportunity_flag);
  if (filter.limit !== undefined) params.set('limit', String(filter.limit));
  const qs = params.toString();
  const res = await apiClient.get<KeywordUniverseRow[]>(
    `/keyword-universe${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function listClusterCounts(): Promise<ClusterCount[]> {
  const res = await apiClient.get<ClusterCount[]>('/keyword-universe/clusters');
  return res.data;
}

export async function refreshKeywordUniverse(): Promise<{ upserted: number }> {
  const res = await apiClient.post<{ upserted: number }>('/keyword-universe/refresh');
  return res.data;
}
