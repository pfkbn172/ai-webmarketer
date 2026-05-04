import { apiClient } from '@/api/client';

export type ReportSummary = {
  id: string;
  period: string;
  report_type: string;
  generated_at: string;
  has_summary: boolean;
  share_token: string | null;
};

export type ReportDetail = {
  id: string;
  period: string;
  report_type: string;
  generated_at: string;
  summary_html: string | null;
  action_plan: Record<string, unknown> | null;
  share_token: string | null;
};

export async function fetchReports(): Promise<ReportSummary[]> {
  return (await apiClient.get<ReportSummary[]>('/reports')).data;
}
export async function fetchReport(id: string): Promise<ReportDetail> {
  return (await apiClient.get<ReportDetail>(`/reports/${id}`)).data;
}
export async function createShareToken(
  id: string,
): Promise<{ share_token: string; public_url_path: string }> {
  return (
    await apiClient.post<{ share_token: string; public_url_path: string }>(
      `/reports/${id}/share`,
    )
  ).data;
}
export async function revokeShareToken(id: string): Promise<void> {
  await apiClient.delete(`/reports/${id}/share`);
}
export function reportPdfUrl(id: string): string {
  return `${apiClient.defaults.baseURL}/reports/${id}/pdf`;
}
export function publicReportPdfUrl(token: string): string {
  return `${apiClient.defaults.baseURL}/public/reports/${token}/pdf`;
}
