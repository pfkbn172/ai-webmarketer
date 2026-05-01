import { apiClient } from '@/api/client';

export type TargetQuery = {
  id: string;
  query_text: string;
  cluster_id: string | null;
  priority: number;
  expected_conversion: number;
  search_intent: string | null;
  is_active: boolean;
};

export async function listQueries(): Promise<TargetQuery[]> {
  const res = await apiClient.get<TargetQuery[]>('/target-queries/');
  return res.data;
}

export async function createQuery(payload: Partial<TargetQuery>): Promise<TargetQuery> {
  const res = await apiClient.post<TargetQuery>('/target-queries/', payload);
  return res.data;
}

export async function deleteQuery(id: string): Promise<void> {
  await apiClient.delete(`/target-queries/${id}`);
}
