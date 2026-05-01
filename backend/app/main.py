from fastapi import FastAPI

from app.api.v1 import health
from app.auth.middleware import AuthMiddleware
from app.settings import settings
from app.utils.logger import configure_logging

configure_logging()

app = FastAPI(
    title="AIウェブマーケター API",
    version="0.1.0",
    docs_url="/api/docs" if settings.env != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.env != "production" else None,
)

app.add_middleware(AuthMiddleware)

# Nginx が /marketer/api/ → 127.0.0.1:3009/api/ にプロキシする想定。
# 本アプリは内部的には /api/v1/* で待ち受ける。
app.include_router(health.router, prefix="/api/v1")
