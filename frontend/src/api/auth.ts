import { apiClient } from '@/api/client';

export type LoginPayload = { email: string; password: string };
export type LoginResponse = {
  user_id: string;
  role: 'admin' | 'client';
  tenant_id: string | null;
  access_token_expires_at: string;
};
export type Me = {
  user_id: string;
  email: string;
  role: 'admin' | 'client';
  tenant_ids: string[];
};

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const res = await apiClient.post<LoginResponse>('/auth/login', payload);
  return res.data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function fetchMe(): Promise<Me> {
  const res = await apiClient.get<Me>('/auth/me');
  return res.data;
}
