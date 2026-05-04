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

// 永続化されたレビュー結果のラッパ。result は StrategicReview / ProbeLoopResult、
// generated_at は ISO8601。
export type StoredRecord<T> = { generated_at: string; result: T };

export async function runReview(): Promise<StoredRecord<StrategicReview>> {
  return (await apiClient.post<StoredRecord<StrategicReview>>('/strategic/review')).data;
}

export async function fetchLatestReview(): Promise<StoredRecord<StrategicReview> | null> {
  return (await apiClient.get<StoredRecord<StrategicReview> | null>('/strategic/review/latest'))
    .data;
}

export async function runProbeLoop(): Promise<StoredRecord<ProbeLoopResult>> {
  return (await apiClient.post<StoredRecord<ProbeLoopResult>>('/strategic/probe-loop')).data;
}

export async function fetchLatestProbeLoop(): Promise<StoredRecord<ProbeLoopResult> | null> {
  return (await apiClient.get<StoredRecord<ProbeLoopResult> | null>('/strategic/probe-loop/latest'))
    .data;
}

export async function fetchCompetitorPatterns(days = 30): Promise<CompetitorPattern[]> {
  return (
    await apiClient.get<CompetitorPattern[]>('/strategic/competitor-patterns', {
      params: { days },
    })
  ).data;
}
