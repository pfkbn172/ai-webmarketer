以下のクエリは、競合は引用されているがクライアントが引用されていません。
それぞれに対して、引用獲得のための推奨アクションを 1〜3 個ずつ挙げてください。

## クライアント
- 名称: {{ tenant_name }}
- ドメイン: {{ domain }}

## 該当クエリと競合
{% for item in opportunities %}
- クエリ: {{ item.query }}
  - 競合の引用例: {{ item.competitor_examples }}
{% endfor %}

## 出力フォーマット(JSON 配列)
[
  {
    "query": "...",
    "actions": [
      {"action": "著者プロフィール強化", "detail": "...", "priority": "high|medium|low"}
    ]
  }
]
JSON のみ返す。
