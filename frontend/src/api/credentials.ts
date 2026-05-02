import { apiClient } from '@/api/client';

export type CredentialStatus = {
  provider: string;
  registered: boolean;
  masked: string | null;
  updated_at: string | null;
  fields: string[];
};

export type CredentialUpsert = {
  api_key?: string;
  base_url?: string;
  user_login?: string;
  app_password?: string;
  site_url?: string;
  property_id?: string;
};

export async function listCredentials(): Promise<CredentialStatus[]> {
  return (await apiClient.get<CredentialStatus[]>('/credentials/')).data;
}

export async function upsertCredential(
  provider: string,
  payload: CredentialUpsert,
): Promise<CredentialStatus> {
  return (await apiClient.put<CredentialStatus>(`/credentials/${provider}`, payload)).data;
}

export async function deleteCredential(provider: string): Promise<void> {
  await apiClient.delete(`/credentials/${provider}`);
}
