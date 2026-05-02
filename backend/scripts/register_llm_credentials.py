"""`.env` に書いた LLM API キーを tenant_credentials に一括登録する。

仕様書 6.x / 設計指針 10.1 に従い、本番運用ではテナント別資格情報が
tenant_credentials に Fernet 暗号化保管されることを前提とする。
.env は「最初の 1 テナント分のフォールバック」用途。

引用モニタの runner._build_clients() は tenant_credentials のみを参照する設計のため、
.env だけ書いても引用モニタは skipped になる。本スクリプトを 1 度実行することで
.env の値を tenant_credentials にコピー登録する。

使い方:
    cd backend
    .venv/bin/python -m scripts.register_llm_credentials \
        --tenant-id 7c59f23a-a94d-4a13-9910-a309d7743c22

オプション:
    --providers gemini openai anthropic perplexity serpapi
        登録対象を絞る(指定なしなら .env に値があるもの全部)

冪等性: 既に登録されている provider は upsert で更新される。
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.enums import CredentialProviderEnum
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.settings import settings


@dataclass(frozen=True, slots=True)
class ProviderEntry:
    cred_provider: CredentialProviderEnum
    env_key: str
    label: str


# .env のキー → tenant_credentials のプロバイダ enum
ENTRIES: list[ProviderEntry] = [
    ProviderEntry(
        CredentialProviderEnum.gemini_ai_engine, "gemini_api_key_ai_engine", "Gemini (AI 処理用)"
    ),
    ProviderEntry(
        CredentialProviderEnum.gemini_citation_monitor,
        "gemini_api_key_citation_monitor",
        "Gemini (引用モニタ用)",
    ),
    ProviderEntry(CredentialProviderEnum.openai, "openai_api_key", "OpenAI (ChatGPT)"),
    ProviderEntry(CredentialProviderEnum.anthropic, "anthropic_api_key", "Anthropic (Claude)"),
    ProviderEntry(CredentialProviderEnum.perplexity, "perplexity_api_key", "Perplexity"),
    ProviderEntry(CredentialProviderEnum.serpapi, "serpapi_key", "SerpApi (AI Overviews)"),
]


def _entries_to_use(filter_names: list[str] | None) -> list[ProviderEntry]:
    if not filter_names:
        return ENTRIES
    wanted = set(filter_names)
    return [e for e in ENTRIES if e.cred_provider.value in wanted]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--providers",
        nargs="+",
        help=(
            "登録対象の credential_provider 名を絞る。例: "
            "--providers gemini_ai_engine openai。"
            "指定なしなら .env に値があるもの全部。"
        ),
    )
    args = parser.parse_args()

    try:
        tenant_uuid = uuid.UUID(args.tenant_id)
    except ValueError:
        print(f"[ERROR] tenant-id が UUID 形式ではありません: {args.tenant_id}", file=sys.stderr)
        return 2

    targets = _entries_to_use(args.providers)
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    registered = 0
    skipped: list[str] = []
    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_uuid)},
        )
        repo = TenantCredentialRepository(session)
        for entry in targets:
            api_key = getattr(settings, entry.env_key, "") or ""
            if not api_key:
                skipped.append(f"{entry.label} (.env の MARKETER_{entry.env_key.upper()} 未設定)")
                continue
            await repo.upsert(
                tenant_uuid,
                entry.cred_provider,
                {"api_key": api_key},
            )
            registered += 1
            print(f"[INFO] {entry.label} を登録")
        await session.commit()
    await engine.dispose()

    print()
    print(f"[DONE] {registered} 件を登録、{len(skipped)} 件スキップ")
    for s in skipped:
        print(f"  - skip: {s}")
    if registered == 0:
        print(
            "[WARN] 1 件も登録できませんでした。.env に MARKETER_*_API_KEY を設定してから "
            "pm2 reload --update-env で反映 → 再実行してください。",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
