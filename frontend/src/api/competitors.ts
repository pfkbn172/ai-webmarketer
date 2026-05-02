import { apiClient } from '@/api/client';

export type Competitor = {
  id: string;
  domain: string;
  brand_name: string | null;
  rss_url: string | null;
  is_active: boolean;
};

export type CompetitorInput = Omit<Competitor, 'id'>;

export async function listCompetitors(): Promise<Competitor[]> {
  return (await apiClient.get<Competitor[]>('/competitors/')).data;
}
export async function createCompetitor(payload: CompetitorInput): Promise<Competitor> {
  return (await apiClient.post<Competitor>('/competitors/', payload)).data;
}
export async function updateCompetitor(
  id: string,
  payload: CompetitorInput,
): Promise<Competitor> {
  return (await apiClient.put<Competitor>(`/competitors/${id}`, payload)).data;
}
export async function deleteCompetitor(id: string): Promise<void> {
  await apiClient.delete(`/competitors/${id}`);
}
