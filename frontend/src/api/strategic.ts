import { apiClient } from '@/api/client';

export type Anomaly = { kind: string; detail: string; severity: 'low' | 'medium' | 'high' };

export type StrategicReview = {
  core_findings?: string[];
  alignments_with_business_context?: string[];
  misalignments?: string[];
  next_actions?: { priority: number; action: string; rationale: string }[];
};

export type ProbeLoopResult = {
  axis_a?: {
    label: string;
    expected_self_citation_rate: number;
    competitive_strength: string;
    stage_fit: string;
    reasoning: string;
    sample_queries: string[];
  };
  axis_b?: {
    label: string;
    expected_self_citation_rate: number;
    competitive_strength: string;
    stage_fit: string;
    reasoning: string;
    sample_queries: string[];
  };
  winner?: string;
  winner_rationale?: string;
};

export type CompetitorPattern = { domain: string; count: number; label: string };

export async function fetchAnomalies(): Promise<Anomaly[]> {
  return (await apiClient.get<Anomaly[]>('/strategic/anomalies')).data;
}

export async function runReview(): Promise<StrategicReview> {
  return (await apiClient.post<StrategicReview>('/strategic/review')).data;
}

export async function runProbeLoop(): Promise<ProbeLoopResult> {
  return (await apiClient.post<ProbeLoopResult>('/strategic/probe-loop')).data;
}

export async function fetchCompetitorPatterns(days = 30): Promise<CompetitorPattern[]> {
  return (
    await apiClient.get<CompetitorPattern[]>('/strategic/competitor-patterns', {
      params: { days },
    })
  ).data;
}
