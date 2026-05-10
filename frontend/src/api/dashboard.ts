import { apiClient } from '@/api/client';

export type ClusterCitation = {
  cluster_id: string;
  total: number;
  self_cited: number;
  rate: number;
};

export type TopQueryRow = {
  query_text: string;
  clicks: number;
  impressions: number;
  ctr: number | null;
  avg_position: number | null;
};

export type HeatmapCell = { llm_provider: string; self_cited: number; total: number };
export type HeatmapRow = {
  query_text: string;
  cluster_id: string | null;
  cells: HeatmapCell[];
};

export type ChannelBreakdown = { channel: string; sessions: number };

export type NextAction = {
  id: string;
  text: string;
  rationale: string | null;
  completed: boolean;
};

export type Objective = {
  key: string;
  label: string;
  target: number;
  current: number;
  progress_pct: number;
};

export type CompetitorPatternMini = { domain: string; count: number; label: string };

export type AiReferralRow = { label: string; source_host: string; sessions: number };

export type PagePerformanceRow = {
  page_path: string;
  title: string | null;
  sessions: number;
  clicks: number;
  impressions: number;
  ctr: number | null;
  avg_position: number | null;
  citation_count: number;
};

export type ChannelCvrRow = {
  channel: string;
  sessions: number;
  inquiries: number;
  cvr: number | null;
};

export type QueryRankChangeRow = {
  query_text: string;
  avg_position_recent: number | null;
  avg_position_prev: number | null;
  delta: number | null;
  impressions_recent: number;
  clicks_recent: number;
};

export type QueryRankChanges = {
  period_days: number;
  rising: QueryRankChangeRow[];
  falling: QueryRankChangeRow[];
};

export type FunnelStage = { status: string; count: number; amount_yen: number };
export type Funnel = {
  period_days: number;
  stages: FunnelStage[];
  cv_rate: number | null;
  avg_amount_yen: number | null;
  cpa_yen: number | null;
};

export type KeywordOpportunity = {
  query_text: string;
  impressions: number;
  avg_position: number | null;
  citation_rate: number;
  cluster_id: string | null;
  recommended_action: 'win' | 'optimize' | 'create' | 'monitor';
};

export type CompetitorContent = {
  domain: string;
  url: string;
  cite_count: number;
  sample_query: string | null;
};

export type AlertRule = {
  id: string;
  metric: 'sessions_drop_pct' | 'citations_drop_pct' | 'inquiries_zero_days' | 'anomaly';
  threshold: number;
  notify_email: string | null;
  notify_slack_webhook: string | null;
  enabled: boolean;
};

export type CvPathRow = {
  channel: string;
  sessions: number;
  inquiries: number;
  cv_rate: number | null;
};

export type PageRankDecayRow = {
  page: string;
  title: string | null;
  avg_position_recent: number | null;
  avg_position_baseline: number | null;
  delta: number | null;
  impressions_recent: number;
};

export type BrandSearchPoint = {
  period: string;
  impressions: number;
  clicks: number;
};

export type IntentRow = {
  intent: 'transactional' | 'navigational' | 'informational' | 'other';
  impressions: number;
  clicks: number;
  queries: number;
  avg_position: number | null;
};

export type SeasonalityCell = {
  weekday: number;
  month: number;
  avg_sessions: number;
  samples: number;
};

export type HourWeekdayCell = {
  weekday: number;
  hour: number;
  sessions: number;
};

export type HourWeekdayHeatmap = {
  period_days: number;
  cells: HourWeekdayCell[];
  peaks: HourWeekdayCell[];
};

export type ReferralRow = {
  source: string;
  medium: string;
  sessions: number;
};

export type ReferralTop = {
  period_days: number;
  total_sessions: number;
  rows: ReferralRow[];
};

export type ReferralHourlyRow = {
  hour: number;
  source: string;
  medium: string;
  sessions: number;
};

export type ReferralDayDetail = {
  target_date: string;
  total_sessions: number;
  daily_breakdown: ReferralRow[];
  hourly_rows: ReferralHourlyRow[];
};

export type DataSourceInfo = {
  key: string;
  label: string;
  provider: string;
  coverage_from: string | null;
  coverage_to: string | null;
  row_count: number;
  last_job_at: string | null;
  job_name: string | null;
};

export type AreaPerformance = {
  cluster_id: string;
  impressions: number;
  clicks: number;
  avg_position: number | null;
  citation_rate: number;
  queries: number;
};

export type PageSpeedRow = {
  page_url: string;
  strategy: 'mobile' | 'desktop';
  performance_score: number | null;
  lcp_ms: number | null;
  cls: number | null;
  inp_ms: number | null;
  measured_at: string;
};

export async function fetchClusterCitation(days = 30): Promise<ClusterCitation[]> {
  return (
    await apiClient.get<ClusterCitation[]>('/dashboard/cluster-citation', {
      params: { days },
    })
  ).data;
}
export async function fetchTopQueries(days = 30, limit = 10): Promise<TopQueryRow[]> {
  return (
    await apiClient.get<TopQueryRow[]>('/dashboard/top-queries', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchHeatmap(days = 28, limit = 5): Promise<HeatmapRow[]> {
  return (
    await apiClient.get<HeatmapRow[]>('/dashboard/citation-heatmap', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchChannelBreakdown(days = 30): Promise<ChannelBreakdown[]> {
  return (
    await apiClient.get<ChannelBreakdown[]>('/dashboard/channel-breakdown', {
      params: { days },
    })
  ).data;
}
export async function fetchNextActions(): Promise<NextAction[]> {
  return (await apiClient.get<NextAction[]>('/dashboard/next-actions')).data;
}
export async function replaceNextActions(items: NextAction[]): Promise<NextAction[]> {
  return (await apiClient.put<NextAction[]>('/dashboard/next-actions', { items })).data;
}
export async function generateNextActionsWithAi(): Promise<NextAction[]> {
  return (await apiClient.post<NextAction[]>('/dashboard/next-actions/from-ai')).data;
}
export async function fetchObjectives(): Promise<Objective[]> {
  return (await apiClient.get<Objective[]>('/dashboard/objectives')).data;
}
export async function upsertObjectives(payload: {
  monthly_sessions?: number;
  monthly_citations?: number;
  monthly_inquiries?: number;
  monthly_contents?: number;
}): Promise<Objective[]> {
  return (await apiClient.put<Objective[]>('/dashboard/objectives', payload)).data;
}
export async function fetchCompetitorPatternsTop(
  days = 30,
): Promise<CompetitorPatternMini[]> {
  return (
    await apiClient.get<CompetitorPatternMini[]>('/dashboard/competitor-patterns-top', {
      params: { days },
    })
  ).data;
}
export async function fetchAiReferrals(days = 30): Promise<AiReferralRow[]> {
  return (
    await apiClient.get<AiReferralRow[]>('/dashboard/ai-referrals', { params: { days } })
  ).data;
}
export async function fetchPagePerformance(
  days = 30,
  limit = 20,
): Promise<PagePerformanceRow[]> {
  return (
    await apiClient.get<PagePerformanceRow[]>('/dashboard/page-performance', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchFunnel(days = 90): Promise<Funnel> {
  return (await apiClient.get<Funnel>('/dashboard/funnel', { params: { days } })).data;
}
export async function fetchKeywordOpportunity(
  days = 30,
  limit = 30,
): Promise<KeywordOpportunity[]> {
  return (
    await apiClient.get<KeywordOpportunity[]>('/dashboard/keyword-opportunity', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchCompetitorContent(
  days = 30,
  limit = 20,
): Promise<CompetitorContent[]> {
  return (
    await apiClient.get<CompetitorContent[]>('/dashboard/competitor-content', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchAlertRules(): Promise<AlertRule[]> {
  return (await apiClient.get<AlertRule[]>('/dashboard/alert-rules')).data;
}
export async function replaceAlertRules(items: AlertRule[]): Promise<AlertRule[]> {
  return (await apiClient.put<AlertRule[]>('/dashboard/alert-rules', { items })).data;
}
export async function fetchCvPaths(days = 90): Promise<CvPathRow[]> {
  return (await apiClient.get<CvPathRow[]>('/dashboard/cv-paths', { params: { days } })).data;
}
export async function fetchPageRankDecay(limit = 20): Promise<PageRankDecayRow[]> {
  return (await apiClient.get<PageRankDecayRow[]>('/dashboard/page-rank-decay', { params: { limit } }))
    .data;
}
export async function fetchBrandSearch(months = 12): Promise<BrandSearchPoint[]> {
  return (await apiClient.get<BrandSearchPoint[]>('/dashboard/brand-search', { params: { months } }))
    .data;
}
export async function fetchSearchIntent(days = 90): Promise<IntentRow[]> {
  return (await apiClient.get<IntentRow[]>('/dashboard/search-intent', { params: { days } })).data;
}
export async function fetchSeasonality(months = 18): Promise<SeasonalityCell[]> {
  return (await apiClient.get<SeasonalityCell[]>('/dashboard/seasonality', { params: { months } }))
    .data;
}
export async function fetchAreaPerformance(days = 90): Promise<AreaPerformance[]> {
  return (
    await apiClient.get<AreaPerformance[]>('/dashboard/area-performance', { params: { days } })
  ).data;
}
export async function fetchPageSpeed(): Promise<PageSpeedRow[]> {
  return (await apiClient.get<PageSpeedRow[]>('/dashboard/page-speed')).data;
}
export async function fetchChannelCvr(days = 30): Promise<ChannelCvrRow[]> {
  return (
    await apiClient.get<ChannelCvrRow[]>('/dashboard/channel-cvr', { params: { days } })
  ).data;
}
export async function fetchQueryRankChanges(
  days = 14,
  limit = 10,
): Promise<QueryRankChanges> {
  return (
    await apiClient.get<QueryRankChanges>('/dashboard/query-rank-changes', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchHourWeekdayHeatmap(days = 90): Promise<HourWeekdayHeatmap> {
  return (
    await apiClient.get<HourWeekdayHeatmap>('/dashboard/hour-weekday-heatmap', {
      params: { days },
    })
  ).data;
}
export async function fetchReferralsTop(days = 30, limit = 15): Promise<ReferralTop> {
  return (
    await apiClient.get<ReferralTop>('/dashboard/referrals', {
      params: { days, limit },
    })
  ).data;
}
export async function fetchReferralsDay(targetDate: string): Promise<ReferralDayDetail> {
  return (
    await apiClient.get<ReferralDayDetail>('/dashboard/referrals/day', {
      params: { target_date: targetDate },
    })
  ).data;
}
export async function fetchDataSources(): Promise<Record<string, DataSourceInfo>> {
  return (
    await apiClient.get<Record<string, DataSourceInfo>>('/dashboard/data-sources')
  ).data;
}

// === 2026-05 追加: GA4 カスタムイベント関連 ============================
//
// 本体側 analytics.js が送るイベント(ai_referral / ai_crawler_visit /
// llms_txt_fetch / contact_confirm_view + conversions)をブレイクダウン
// して可視化する。GA4 ディメンション登録から 24〜48 時間で伝播するため、
// それまでは空配列が正常系。

export type AiReferralEventRow = {
  ai_referrer_domain: string;
  event_count: number;
};

export async function fetchAiReferralEvents(
  days = 30,
  limit = 20,
): Promise<AiReferralEventRow[]> {
  return (
    await apiClient.get<AiReferralEventRow[]>('/dashboard/ai-referral-events', {
      params: { days, limit },
    })
  ).data;
}

export type AiCrawlerByName = { crawler_name: string; event_count: number };
export type AiCrawlerSeriesPoint = {
  date: string;
  crawler_name: string;
  event_count: number;
};
export type AiCrawlerVisitsOut = {
  total: number;
  by_crawler: AiCrawlerByName[];
  series: AiCrawlerSeriesPoint[];
};

export async function fetchAiCrawlerVisits(days = 30): Promise<AiCrawlerVisitsOut> {
  return (
    await apiClient.get<AiCrawlerVisitsOut>('/dashboard/ai-crawler-visits', {
      params: { days },
    })
  ).data;
}

export type AiCrawlerPageRow = {
  page_path: string;
  event_count: number;
  top_crawler: string;
};

export async function fetchAiCrawlerPages(
  days = 30,
  limit = 10,
): Promise<AiCrawlerPageRow[]> {
  return (
    await apiClient.get<AiCrawlerPageRow[]>('/dashboard/ai-crawler-pages', {
      params: { days, limit },
    })
  ).data;
}

export type LlmsTxtFetchByCrawler = { crawler_name: string; event_count: number };
export type LlmsTxtFetchSeriesPoint = { date: string; total: number };
export type LlmsTxtFetchOut = {
  total: number;
  by_crawler: LlmsTxtFetchByCrawler[];
  series: LlmsTxtFetchSeriesPoint[];
};

export async function fetchLlmsTxtFetches(days = 30): Promise<LlmsTxtFetchOut> {
  return (
    await apiClient.get<LlmsTxtFetchOut>('/dashboard/llms-txt-fetches', {
      params: { days },
    })
  ).data;
}

export type ContactFunnelStep = {
  label: string;
  key: string;
  count: number;
  drop_off_pct: number | null;
};

export type ContactFunnel = {
  period_days: number;
  steps: ContactFunnelStep[];
};

export async function fetchContactFunnel(days = 30): Promise<ContactFunnel> {
  return (
    await apiClient.get<ContactFunnel>('/dashboard/contact-funnel', {
      params: { days },
    })
  ).data;
}
