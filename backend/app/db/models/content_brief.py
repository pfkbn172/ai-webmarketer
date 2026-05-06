"""採用キーワード群から AI が生成したコンテンツブリーフ。

title / meta / h2 構成 / 対策キーワード割当てを保持し、wordpress_publisher で
下書き化されたら wp_draft_id を記録する。
"""

from typing import Any

from sqlalchemy import Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, UpdatedTimestampsMixin


class ContentBrief(Base, IdMixin, TenantMixin, UpdatedTimestampsMixin):
    __tablename__ = "content_briefs"
    __table_args__ = (
        Index("ix_cb_tenant_created", "tenant_id", "created_at"),
        Index("ix_cb_tenant_status", "tenant_id", "status"),
    )

    primary_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    # 採用キーワードが属するクラスタ群(LP/記事1本が複数クラスタを横断するケースも想定)
    cluster_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    selected_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    meta_description: Mapped[str | None] = mapped_column(Text)
    h2_outline: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    related_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    competitor_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    target_url_slug: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    # 'draft' | 'adopted' | 'published'
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    wp_draft_id: Mapped[int | None] = mapped_column(Integer)
