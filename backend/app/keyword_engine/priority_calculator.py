"""keyword_universe の priority_score と opportunity_flag を計算する。

設計: docs/feature_keyword_universe_plan.md §3.4

priority_score =
    log10(gsc_imp_12m + 1) * 30                         # 実需(自社既知)
  + log10(suggest_derivative_count + 1) * 20            # 派生豊富さ
  + competitor_coverage_count * 5                       # 競合カバー
  + max(0, (51 - COALESCE(gsc_avg_position, 100))) * 0.5 # 上位寄り加点
  + (1 - COALESCE(llm_self_cite_rate, 0)) * 10          # 引用されていない=機会
  - (is_geographic AND gsc_imp_12m < 5) * 15            # 地域系で実需0は減点
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriorityInputs:
    gsc_imp_12m: int
    gsc_avg_position: float | None
    suggest_derivative_count: int
    competitor_coverage_count: int
    llm_self_cite_rate: float | None
    is_geographic: bool


def calculate_score(inputs: PriorityInputs) -> float:
    score = 0.0
    score += math.log10(inputs.gsc_imp_12m + 1) * 30
    score += math.log10(inputs.suggest_derivative_count + 1) * 20
    score += inputs.competitor_coverage_count * 5
    pos = inputs.gsc_avg_position if inputs.gsc_avg_position is not None else 100.0
    score += max(0.0, 51.0 - float(pos)) * 0.5
    self_cite = inputs.llm_self_cite_rate if inputs.llm_self_cite_rate is not None else 0.0
    score += (1.0 - float(self_cite)) * 10
    if inputs.is_geographic and inputs.gsc_imp_12m < 5:
        score -= 15
    return round(score, 2)


def determine_opportunity_flag(inputs: PriorityInputs) -> str | None:
    """ハイライトすべき機会パターンを判定する。
    優先順序:
      high_demand_no_coverage: サジェスト多いが自社imp少ない(=新規LP機会)
      near_top_3:              既に4-15位にいて imp >= 50(=リライト機会)
      low_demand:              派生少+imp少+競合カバーなし(=やる価値なし)
    """
    # high_demand_no_coverage:
    #   派生 seed 数 >= 2(=複数シードから出現する横断ワード) かつ
    #   自社 GSC imp が低い(=自サイトはまだ拾えていない) を機会として拾う。
    #   閾値の根拠: Phase 1 のサジェスト収集で 40 シード × 2 エンジンを回した結果、
    #   派生 seed 数の最大は 3。閾値 5 は厳しすぎるので 2 を採用する。
    if inputs.suggest_derivative_count >= 2 and inputs.gsc_imp_12m < 10:
        return "high_demand_no_coverage"
    if (
        inputs.gsc_avg_position is not None
        and 4 <= float(inputs.gsc_avg_position) <= 15
        and inputs.gsc_imp_12m >= 50
    ):
        return "near_top_3"
    if (
        inputs.suggest_derivative_count <= 1
        and inputs.gsc_imp_12m < 3
        and inputs.competitor_coverage_count == 0
    ):
        return "low_demand"
    return None
