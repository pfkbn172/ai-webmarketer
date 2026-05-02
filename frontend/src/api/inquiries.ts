import { apiClient } from '@/api/client';

export type InquirySourceChannel = 'web' | 'email' | 'phone' | 'ai' | 'other';
export type AiOrigin = 'chatgpt' | 'claude' | 'perplexity' | 'gemini' | 'aio';
export type InquiryStatus = 'new' | 'in_progress' | 'contracted' | 'lost';

export type Inquiry = {
  id: string;
  received_at: string | null;
  industry: string | null;
  company_size: string | null;
  content_text: string;
  source_channel: InquirySourceChannel;
  ai_origin: AiOrigin | null;
  status: InquiryStatus;
};

export type InquiryInput = Omit<Inquiry, 'id'> & { received_at?: string | null };

export async function listInquiries(): Promise<Inquiry[]> {
  return (await apiClient.get<Inquiry[]>('/inquiries/')).data;
}
export async function createInquiry(payload: Partial<InquiryInput>): Promise<Inquiry> {
  return (await apiClient.post<Inquiry>('/inquiries/', payload)).data;
}
export async function updateInquiryStatus(id: string, status: InquiryStatus): Promise<Inquiry> {
  return (await apiClient.patch<Inquiry>(`/inquiries/${id}/status`, { status })).data;
}
