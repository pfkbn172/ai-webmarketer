以下の問い合わせ文面を構造化してください。

## 問い合わせ本文
{{ raw_text }}

## 流入元(参考)
{{ source_hint }}

## 出力フォーマット(JSON)
{
  "industry": "業種(推定)",
  "company_size": "企業規模(従業員数の概数 / 'small'|'medium'|'large')",
  "intent": "問い合わせ意図の要約",
  "ai_origin": "chatgpt/claude/perplexity/gemini/aio のいずれか、不明なら null"
}
JSON のみ返す。不明フィールドは null。
