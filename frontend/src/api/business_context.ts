import { apiClient } from '@/api/client';

export type BusinessContext = {
  stage: string | null;
  geographic_base: string[];
  geographic_expansion: string[];
  unique_value: string[];
  primary_offerings: string[];
  target_customer: string | null;
  weak_segments: string[];
  strong_segments: string[];
  compliance_constraints: string[];
};

export async function fetchBusinessContext(): Promise<BusinessContext> {
  return (await apiClient.get<BusinessContext>('/business-context/')).data;
}

export async function updateBusinessContext(
  payload: BusinessContext,
): Promise<BusinessContext> {
  return (await apiClient.put<BusinessContext>('/business-context/', payload)).data;
}

export async function aiHearing(freeText: string): Promise<BusinessContext> {
  return (
    await apiClient.post<BusinessContext>('/business-context/ai-hearing', {
      free_text: freeText,
    })
  ).data;
}
