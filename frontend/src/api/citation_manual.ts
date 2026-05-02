import { apiClient } from '@/api/client';

export type LLMProvider = 'chatgpt' | 'claude' | 'perplexity' | 'gemini' | 'aio';

export type ManualCitationInput = {
  query_id: string;
  llm_provider: LLMProvider;
  response_text: string;
  cited_urls: string[];
  query_date?: string;
};

export type ManualCitationResult = {
  id: string;
  self_cited: boolean;
  self_match_reason: string | null;
  competitor_cited: { domain: string; count: number }[];
};

export async function submitManualCitation(
  payload: ManualCitationInput,
): Promise<ManualCitationResult> {
  return (await apiClient.post<ManualCitationResult>('/citation-logs/manual/', payload)).data;
}
