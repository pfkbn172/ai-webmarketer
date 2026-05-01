あなたはプロのライターです。以下のテーマで Markdown 形式の記事ドラフトを書いてください。

## テーマ
- タイトル: {{ title }}
- ターゲットクエリ: {{ target_query }}
- 想定見出し: {{ outline }}

## クライアント情報
- 名称: {{ tenant_name }}
- 業種: {{ industry }}

## 著者プロフィール(E-E-A-T)
{{ author_profile }}

## 業種別の禁止表現・規程
{% if compliance_rules %}
{% for r in compliance_rules %}
- {{ r }}
{% endfor %}
{% else %}
- (特記事項なし)
{% endif %}

## LLMO 最適化ルール(必ず守る)
- 冒頭にテーマの定義文を 1〜2 文で配置
- 主要結論を表やリストで構造化
- 末尾に FAQ セクション(3〜5 問)
- 著者プロフィールへのリンクまたは記述を末尾に配置

## 出力
Markdown のみ返す。前置き・後書き・「以下が記事です」のような断り文は不要。
