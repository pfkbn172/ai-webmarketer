あなたは中小企業向け SEO/LLMO の戦略コンサルタントです。
以下の事業者について、AI 検索(ChatGPT/Claude/Perplexity/Gemini)で
**現実的に引用される可能性のある**ターゲットクエリを 15〜20 本提案してください。

## 事業者プロフィール
- 名称: {{ tenant_name }}
- 業種: {{ industry }}
- ドメイン: {{ domain }}
- 事業ステージ: {{ stage }}
- 拠点地域: {{ geographic_base }}
- 拡大目標地域: {{ geographic_expansion }}
- 独自性・強み: {{ unique_value }}
- 主要サービス: {{ primary_offerings }}
- ターゲット顧客: {{ target_customer }}
- 弱点セグメント(避けるべき広域クエリ): {{ weak_segments }}
- 強いセグメント(勝てる土俵): {{ strong_segments }}

## 既存ターゲットクエリ(参考、重複を避ける)
{% if existing_queries %}
{% for q in existing_queries %}
- {{ q }}
{% endfor %}
{% else %}
- (なし)
{% endif %}

## 📊 データ駆動キーワードユニバース(優先度上位の実データ)

これは GSC 実績 + Google/Bing サジェスト派生 + 競合カバー + LLM 引用率 を統合した
事実ベースのキーワード辞書です。**この上位データを尊重した上で、データに無い切り口を補完してください**。

{% if universe_top %}
| キーワード | クラスタ | スコア | imp(12m) | 順位 | 派生 | 競合 | 機会 |
|---|---|---|---|---|---|---|---|
{% for u in universe_top %}
| {{ u.keyword }} | {{ u.cluster_ids | join(',') }} | {{ u.priority_score }} | {{ u.gsc_imp_12m }} | {{ u.gsc_avg_position or '-' }} | {{ u.suggest_derivative_count }} | {{ u.competitor_coverage_count }} | {{ u.opportunity_flag or '-' }} |
{% endfor %}
{% else %}
(まだユニバース未集計)
{% endif %}

### クラスタ別件数(参考)
{% if clusters_summary %}
{% for c in clusters_summary %}
- {{ c.cluster_id }}: {{ c.rows }} 件
{% endfor %}
{% else %}
- (集計なし)
{% endif %}

## 提案ルール

1. **事業ステージが solo / micro の場合は、広域クエリ(「中小企業 DX コンサル」のような 3 語の一般語)を避ける**
2. **ユニバース上位データを最優先で参照**: priority_score の高いキーワードや opportunity_flag = 'high_demand_no_coverage' / 'near_top_3' は積極的に採用候補に。
3. **拠点地域 × サービスのロングテール**を中心に(例: 「天王寺区 IT DX サポート」)
4. **拡大目標地域 × サービス**も含める(将来の引用獲得を狙う)
5. **独自性を活かせるクエリ**を 2〜3 本含める(タイ進出 / 特定業種経験等)
6. **比較・観測用クエリ**(競合動向観察用)を 3〜5 本含める
7. クエリは 4〜6 語の自然な日本語検索表現にする
8. **reasoning 欄には必ず根拠データを 1 つ以上引用する**(例: 「universe で imp=118・派生=5・near_top_3」「拠点周辺で競合カバー 0」「自社強みのタイ経験を活用」)

## 出力フォーマット(JSON 配列、追加コメント不要)

[
  {
    "query_text": "天王寺区 IT DX サポート",
    "cluster_id": "local_district",
    "priority": 5,
    "expected_conversion": 5,
    "search_intent": "地元での IT/DX サポート会社探し",
    "reasoning": "universe で priority_score=82, gsc_imp=51, 派生 derivative=2, 競合カバー 0 — 拠点地域×主要サービスのロングテールで競合不在の獲得余地大"
  }
]

cluster_id は以下のいずれか:
- local_district: 拠点地域系
- local_expand: 拡大目標地域系
- unique_value: 独自性活用系
- competitive: 比較・観測系
- industry_test: 業種特化テスト用(弱点セグメント、効果測定用)

priority と expected_conversion は 1〜5(勝てる確度・成約期待度)。
