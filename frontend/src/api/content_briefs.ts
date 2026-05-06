import { apiClient } from '@/api/client';

export type H2Item = {
  h2: string;
  target_keywords: string[];
  rationale: string | null;
};

export type ContentBrief = {
  id: string;
  primary_keyword: string;
  cluster_ids: string[];
  selected_keywords: string[];
  title: string;
  meta_description: string | null;
  h2_outline: H2Item[];
  related_keywords: string[];
  target_url_slug: string | null;
  rationale: string | null;
  status: 'draft' | 'adopted' | 'published';
  wp_draft_id: number | null;
  created_at: string;
  updated_at: string;
};

export type GeneratePayload = {
  primary_keyword: string;
  related_keyword_ids: string[];
};

export async function generateBrief(payload: GeneratePayload): Promise<ContentBrief> {
  const res = await apiClient.post<ContentBrief>('/content-briefs/generate', payload);
  return res.data;
}

export async function listBriefs(status?: string): Promise<ContentBrief[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  const res = await apiClient.get<ContentBrief[]>(`/content-briefs${qs}`);
  return res.data;
}

export async function getBrief(id: string): Promise<ContentBrief> {
  const res = await apiClient.get<ContentBrief>(`/content-briefs/${id}`);
  return res.data;
}

export async function deleteBrief(id: string): Promise<void> {
  await apiClient.delete(`/content-briefs/${id}`);
}

export async function publishBriefToWp(
  id: string,
): Promise<{ wp_draft_id: number; wp_post_url: string | null }> {
  const res = await apiClient.post<{ wp_draft_id: number; wp_post_url: string | null }>(
    `/content-briefs/${id}/publish-wp`,
  );
  return res.data;
}
