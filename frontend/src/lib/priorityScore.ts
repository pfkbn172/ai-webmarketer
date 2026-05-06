/**
 * priority_score の計算内訳をフロント側で再計算する。
 * バックエンドの app/keyword_engine/priority_calculator.py と同じ式を使う。
 *
 *   priority_score =
 *       log10(gsc_imp_12m + 1) * 30
 *     + log10(suggest_derivative_count + 1) * 20
 *     + competitor_coverage_count * 5
 *     + max(0, 51 - (gsc_avg_position ?? 100)) * 0.5
 *     + (1 - (llm_self_cite_rate ?? 0)) * 10
 *     - is_geographic && gsc_imp_12m < 5 ? 15 : 0
 */

export type PriorityBreakdown = {
  imp_score: number;
  derivative_score: number;
  competitor_score: number;
  position_score: number;
  llm_opportunity_score: number;
  geo_penalty: number;
  total: number;
};

export function computeBreakdown(input: {
  gsc_imp_12m: number;
  gsc_avg_position: number | null;
  suggest_derivative_count: number;
  competitor_coverage_count: number;
  llm_self_cite_rate: number | null;
  is_geographic: boolean;
}): PriorityBreakdown {
  const imp_score = Math.log10(input.gsc_imp_12m + 1) * 30;
  const derivative_score = Math.log10(input.suggest_derivative_count + 1) * 20;
  const competitor_score = input.competitor_coverage_count * 5;
  const pos = input.gsc_avg_position ?? 100;
  const position_score = Math.max(0, 51 - pos) * 0.5;
  const self_cite = input.llm_self_cite_rate ?? 0;
  const llm_opportunity_score = (1 - self_cite) * 10;
  const geo_penalty =
    input.is_geographic && input.gsc_imp_12m < 5 ? -15 : 0;

  const total =
    imp_score +
    derivative_score +
    competitor_score +
    position_score +
    llm_opportunity_score +
    geo_penalty;

  const round = (n: number) => Math.round(n * 100) / 100;
  return {
    imp_score: round(imp_score),
    derivative_score: round(derivative_score),
    competitor_score: round(competitor_score),
    position_score: round(position_score),
    llm_opportunity_score: round(llm_opportunity_score),
    geo_penalty: round(geo_penalty),
    total: round(total),
  };
}
