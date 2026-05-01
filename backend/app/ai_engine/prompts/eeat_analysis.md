{{ tenant_name }} の著者プロフィールを評価してください。

## 著者プロフィール
{{ author_profile }}

## 公開記事(直近 30 日)
{{ recent_contents }}

## 評価軸(E-E-A-T)
- Experience(経験): 一次情報・実体験の根拠があるか
- Expertise(専門性): 専門領域が明示されているか
- Authoritativeness(権威性): 第三者からの評価・引用があるか
- Trustworthiness(信頼性): 連絡先・所属組織が明確か

## 出力フォーマット(JSON)
{
  "scores": {"experience": 0-100, "expertise": 0-100, "authoritativeness": 0-100, "trustworthiness": 0-100},
  "gaps": [{"axis": "...", "issue": "...", "improvement": "..."}]
}
JSON のみ返す。
