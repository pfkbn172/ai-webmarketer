import { apiClient } from '@/api/client';

export type AuthorProfile = {
  id: string;
  name: string;
  job_title: string | null;
  works_for: string | null;
  alumni_of: string[];
  credentials: string[];
  expertise: string[];
  publications: { title?: string; url?: string }[];
  speaking_engagements: { title?: string; url?: string }[];
  awards: string[];
  bio_short: string | null;
  bio_long: string | null;
  social_profiles: string[];
  is_primary: boolean;
};

export type AuthorProfileInput = Omit<AuthorProfile, 'id'>;

export async function listAuthors(): Promise<AuthorProfile[]> {
  return (await apiClient.get<AuthorProfile[]>('/author-profiles/')).data;
}
export async function createAuthor(payload: AuthorProfileInput): Promise<AuthorProfile> {
  return (await apiClient.post<AuthorProfile>('/author-profiles/', payload)).data;
}
export async function updateAuthor(
  id: string,
  payload: AuthorProfileInput,
): Promise<AuthorProfile> {
  return (await apiClient.put<AuthorProfile>(`/author-profiles/${id}`, payload)).data;
}
export async function deleteAuthor(id: string): Promise<void> {
  await apiClient.delete(`/author-profiles/${id}`);
}
