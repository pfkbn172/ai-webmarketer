"""問い合わせを AI で構造化する(industry / size / intent / ai_origin)。"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.enums import AIUseCaseEnum
from app.utils.logger import get_logger

log = get_logger(__name__)


async def structure_inquiry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    raw_text: str,
    source_hint: str = "",
) -> dict:
    prompt = render(
        "inquiry_structuring.md",
        {"raw_text": raw_text, "source_hint": source_hint},
    )
    try:
        provider = await AIProviderFactory.get_for_use_case(
            session, tenant_id, AIUseCaseEnum.inquiry_structuring
        )
        res = await provider.generate(
            system_prompt="You are a CRM data extraction assistant.",
            user_prompt=prompt,
            response_format="json",
            max_tokens=500,
            temperature=0.2,
        )
        return json.loads(res.text)
    except Exception as exc:
        log.warning("inquiry_structuring_failed", error=str(exc))
        return {"industry": None, "company_size": None, "intent": None, "ai_origin": None}
