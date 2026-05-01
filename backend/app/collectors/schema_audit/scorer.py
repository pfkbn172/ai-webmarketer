"""JSON-LD ブロックの充足度スコアリング。

- Article: headline / author / datePublished / image / publisher が必須
- FAQPage: mainEntity 配列が必須
- Person: name / jobTitle / worksFor / sameAs などが揃うほど高スコア
- Organization: name / url が必須
- BreadcrumbList: itemListElement 配列が必須

各 type ごとに 0〜100 のスコアを出し、平均または最大を total_score にする。
"""

from dataclasses import dataclass, field
from typing import Any

ARTICLE_FIELDS = ["headline", "author", "datePublished", "image", "publisher"]
PERSON_FIELDS = ["name", "jobTitle", "worksFor", "sameAs", "alumniOf", "hasCredential"]
ORG_FIELDS = ["name", "url"]


@dataclass(frozen=True, slots=True)
class AuditScore:
    score: int  # 0..100(主要 type の平均)
    missing_fields: list[dict[str, Any]] = field(default_factory=list)


def _coverage(present: dict, required: list[str]) -> tuple[int, list[str]]:
    missing = [k for k in required if not present.get(k)]
    coverage = round(100 * (1 - len(missing) / max(1, len(required))))
    return coverage, missing


def score_blocks(blocks: list[dict]) -> AuditScore:
    if not blocks:
        return AuditScore(score=0, missing_fields=[{"type": "any", "missing": ["all"]}])

    scores: list[int] = []
    missing_all: list[dict[str, Any]] = []

    for b in blocks:
        t = b.get("@type") or ""
        if isinstance(t, list):
            t = t[0]

        if t == "Article":
            cov, m = _coverage(b, ARTICLE_FIELDS)
            scores.append(cov)
            if m:
                missing_all.append({"type": "Article", "missing": m})
        elif t == "FAQPage":
            ok = isinstance(b.get("mainEntity"), list) and bool(b.get("mainEntity"))
            scores.append(100 if ok else 0)
            if not ok:
                missing_all.append({"type": "FAQPage", "missing": ["mainEntity"]})
        elif t == "Person":
            cov, m = _coverage(b, PERSON_FIELDS)
            scores.append(cov)
            if m:
                missing_all.append({"type": "Person", "missing": m})
        elif t == "Organization":
            cov, m = _coverage(b, ORG_FIELDS)
            scores.append(cov)
            if m:
                missing_all.append({"type": "Organization", "missing": m})
        elif t == "BreadcrumbList":
            ok = isinstance(b.get("itemListElement"), list) and bool(
                b.get("itemListElement")
            )
            scores.append(100 if ok else 0)
            if not ok:
                missing_all.append(
                    {"type": "BreadcrumbList", "missing": ["itemListElement"]}
                )

    total = round(sum(scores) / max(1, len(scores))) if scores else 0
    return AuditScore(score=total, missing_fields=missing_all)
