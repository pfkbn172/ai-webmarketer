"""prompt_templates テーブルにファイル参照を初期投入する。

実行: cd backend && .venv/bin/python -m scripts.seed_prompt_templates
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.enums import AIUseCaseEnum
from app.db.models.prompt_template import PromptTemplate
from app.settings import settings

TEMPLATES = [
    (AIUseCaseEnum.monthly_report, "monthly_report.md", "月次レポート生成"),
    (AIUseCaseEnum.weekly_summary, "weekly_summary.md", "週次サマリ生成"),
    (AIUseCaseEnum.theme_suggestion, "theme_suggestion.md", "コンテンツテーマ提案"),
    (AIUseCaseEnum.content_draft, "content_draft.md", "記事ドラフト生成"),
    (AIUseCaseEnum.compliance_check, "compliance_check.md", "業種別規程チェック"),
    (AIUseCaseEnum.inquiry_structuring, "inquiry_structuring.md", "問い合わせ構造化"),
    (AIUseCaseEnum.eeat_analysis, "eeat_analysis.md", "E-E-A-T 分析"),
    (AIUseCaseEnum.citation_opportunity, "citation_opportunity.md", "引用機会分析"),
]


async def main() -> int:
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        for use_case, file_name, name in TEMPLATES:
            existing = (
                await session.scalars(
                    select(PromptTemplate).where(
                        PromptTemplate.use_case == use_case,
                        PromptTemplate.version == 1,
                    )
                )
            ).one_or_none()
            if existing:
                print(f"[SKIP] {use_case.value} v1 既存")
                continue
            session.add(
                PromptTemplate(
                    name=name,
                    use_case=use_case,
                    version=1,
                    file_path=file_name,
                    is_active=True,
                )
            )
            print(f"[INSERT] {use_case.value} v1 -> {file_name}")
        await session.commit()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
