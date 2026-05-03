import { apiClient } from '@/api/client';
import type { TargetQuery } from '@/api/queries';

export type QuerySuggestion = {
  query_text: string;
  cluster_id: string | null;
  priority: number;
  expected_conversion: number;
  search_intent: string | null;
  reasoning: string | null;
};

export async function suggestQueries(): Promise<QuerySuggestion[]> {
  return (await apiClient.post<QuerySuggestion[]>('/target-queries/suggest')).data;
}

export async function bulkAdoptQueries(
  queries: QuerySuggestion[],
): Promise<TargetQuery[]> {
  return (
    await apiClient.post<TargetQuery[]>('/target-queries/bulk-adopt', { queries })
  ).data;
}
