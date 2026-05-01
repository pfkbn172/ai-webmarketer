"""構造化ログ(JSON 形式)。

設計指針 8.1 で必須:
- timestamp / level / tenant_id / request_id / module / message / extra
- tenant_id と request_id は contextvar から自動付与
- 認証情報(API キー、トークン、パスワード)は出力しない(各呼び出し箇所で除外する責務)
- AI 生成の長文は別ログに分離(本ロガーには summary のみ)

使い方:
    from app.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("citation_collected", query_id=str(qid), llm="chatgpt", count=3)
"""

import logging
import sys

import structlog
from structlog.types import EventDict, Processor

from app.auth.tenant_context import get_context
from app.settings import settings


def _add_tenant_context(_logger, _name: str, event_dict: EventDict) -> EventDict:
    ctx = get_context()
    event_dict["tenant_id"] = str(ctx.tenant_id) if ctx.tenant_id else None
    event_dict["user_id"] = str(ctx.user_id) if ctx.user_id else None
    event_dict["request_id"] = ctx.request_id
    return event_dict


def configure_logging() -> None:
    """アプリ起動時に 1 度だけ呼ぶ。main.py / worker entrypoint で実行。"""
    is_prod = settings.env == "production"

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_tenant_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if is_prod
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
