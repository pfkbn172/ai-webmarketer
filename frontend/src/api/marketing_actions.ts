import { apiClient } from '@/api/client';

export type MarketingActionCategory =
  | 'content_publish'
  | 'seo_optimize'
  | 'ad_campaign'
  | 'pr'
  | 'event'
  | 'other';

export type MarketingAction = {
  id: string;
  action_date: string; // YYYY-MM-DD
  category: MarketingActionCategory;
  title: string;
  description: string | null;
};

export type MarketingActionInput = {
  action_date: string;
  category: MarketingActionCategory;
  title: string;
  description?: string | null;
};

export async function fetchMarketingActions(args: { start?: string; end?: string } = {}): Promise<
  MarketingAction[]
> {
  const params: Record<string, string> = {};
  if (args.start) params.start = args.start;
  if (args.end) params.end = args.end;
  return (await apiClient.get<MarketingAction[]>('/marketing-actions', { params })).data;
}

export async function createMarketingAction(
  input: MarketingActionInput,
): Promise<MarketingAction> {
  return (await apiClient.post<MarketingAction>('/marketing-actions', input)).data;
}

export async function updateMarketingAction(
  id: string,
  patch: Partial<MarketingActionInput>,
): Promise<MarketingAction> {
  return (await apiClient.patch<MarketingAction>(`/marketing-actions/${id}`, patch)).data;
}

export async function deleteMarketingAction(id: string): Promise<void> {
  await apiClient.delete(`/marketing-actions/${id}`);
}

export const CATEGORY_LABEL: Record<MarketingActionCategory, string> = {
  content_publish: '記事公開',
  seo_optimize: 'SEO 改善',
  ad_campaign: '広告',
  pr: 'プレス・露出',
  event: 'イベント',
  other: 'その他',
};

// グラフのマーカーとタイムラインのバッジで使う共通カラー。
// Tailwind のパレットから視認性の高い色を選定。
export const CATEGORY_COLOR: Record<MarketingActionCategory, string> = {
  content_publish: '#8b5cf6', // violet-500: 記事公開
  seo_optimize: '#10b981', // emerald-500: SEO 改善
  ad_campaign: '#f59e0b', // amber-500: 広告
  pr: '#ef4444', // red-500: プレス・露出
  event: '#3b82f6', // blue-500: イベント
  other: '#6b7280', // gray-500: その他
};
