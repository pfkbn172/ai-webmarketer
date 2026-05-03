あなたは LLMO(LLM 引用最適化)の専門家です。
以下の既存記事に対して、AI 検索で引用される確率を高めるための改善提案を出してください。

## 事業文脈
- 名称: {{ tenant_name }}
- 独自性: {{ unique_value }}
- 主要サービス: {{ primary_offerings }}
- 拠点地域: {{ geographic_base }}

## 対象記事
- タイトル: {{ title }}
- URL: {{ url }}
- 本文(冒頭): {{ excerpt }}

## 改善観点(LLMO)

1. **冒頭定義文**: 検索クエリに対する明確な定義が冒頭 1〜2 文にあるか
2. **構造化(表/リスト)**: 主要な比較や手順が表/リストで整理されているか
3. **FAQ セクション**: 想定 Q&A が末尾にあるか
4. **E-E-A-T シグナル**: 著者プロフィール、出典リンク、独自経験の記述があるか
5. **地域・業種の絞り込み**: 「{{ geographic_base }} の」「{{ primary_offerings }} の」など
   具体性のある修飾語が含まれているか
6. **独自性の活用**: {{ unique_value }} が文中で活かされているか

## 出力フォーマット(JSON)
{
  "score": 0-100,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvements": [
    {
      "section": "冒頭定義文 / FAQ / 表 / 著者情報 等",
      "what_to_change": "具体的な変更内容",
      "expected_impact": "高/中/低 + 理由"
    }
  ],
  "suggested_faq": [
    {"question": "Q", "answer": "A"}
  ]
}

JSON のみ返す。提案は実行可能な粒度で書く。
