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

## 提案ルール

1. **事業ステージが solo / micro の場合は、広域クエリ(「中小企業 DX コンサル」のような 3 語の一般語)を避ける**
2. **拠点地域 × サービスのロングテール**を中心に(例: 「天王寺区 IT DX サポート」)
3. **拡大目標地域 × サービス**も含める(将来の引用獲得を狙う)
4. **独自性を活かせるクエリ**を 2〜3 本含める(タイ進出 / 特定業種経験等)
5. **比較・観測用クエリ**(競合動向観察用)を 3〜5 本含める
6. クエリは 4〜6 語の自然な日本語検索表現にする

## 出力フォーマット(JSON 配列、追加コメント不要)

[
  {
    "query_text": "天王寺区 IT DX サポート",
    "cluster_id": "local_district",
    "priority": 5,
    "expected_conversion": 5,
    "search_intent": "地元での IT/DX サポート会社探し",
    "reasoning": "拠点地域 × 主要サービスのロングテール、勝てる土俵"
  }
]

cluster_id は以下のいずれか:
- local_district: 拠点地域系
- local_expand: 拡大目標地域系
- unique_value: 独自性活用系
- competitive: 比較・観測系
- industry_test: 業種特化テスト用(弱点セグメント、効果測定用)

priority と expected_conversion は 1〜5(勝てる確度・成約期待度)。
