import { apiClient } from '@/api/client';

export type JobLog = {
  id: string;
  job_name: string;
  status: 'running' | 'success' | 'failed';
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  error_text: string | null;
};

export async function listJobs(hours = 72, limit = 200): Promise<JobLog[]> {
  const res = await apiClient.get<JobLog[]>(
    `/system/jobs?hours=${hours}&limit=${limit}`,
  );
  return res.data;
}
