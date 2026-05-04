from fastapi import FastAPI

from app.api.v1 import (
    auth,
    author_profiles,
    business_context,
    citation_logs,
    citation_manual,
    competitors,
    credentials,
    dashboard,
    exports,
    health,
    inquiries,
    kpi,
    strategic,
    target_queries,
    tenants,
)
from app.auth.middleware import AuthMiddleware
from app.settings import settings
from app.utils.logger import configure_logging
from app.webhook import inquiry as wh_inquiry
from app.webhook import wordpress as wh_wordpress

configure_logging()

app = FastAPI(
    title="AIウェブマーケター API",
    version="0.2.0",
    docs_url="/api/docs" if settings.env != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.env != "production" else None,
)

app.add_middleware(AuthMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(target_queries.router, prefix="/api/v1")
app.include_router(citation_logs.router, prefix="/api/v1")
app.include_router(citation_manual.router, prefix="/api/v1")
app.include_router(kpi.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(author_profiles.router, prefix="/api/v1")
app.include_router(competitors.router, prefix="/api/v1")
app.include_router(credentials.router, prefix="/api/v1")
app.include_router(inquiries.router, prefix="/api/v1")
app.include_router(business_context.router, prefix="/api/v1")
app.include_router(strategic.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

# Webhook(認証不要、テナント ID は URL に含める)
app.include_router(wh_wordpress.router, prefix="/webhook")
app.include_router(wh_inquiry.router, prefix="/webhook")
