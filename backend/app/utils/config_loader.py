"""環境変数 + DB 設定の統合ローダー。

設計指針 2.1 で必須モジュールに含まれる。
Phase 1 段階では Pydantic Settings(`app.settings.settings`)が環境変数を扱い、
本モジュールは「DB の Settings テーブル」(将来的にテナントごと設定を持つ)から
値を引いてくる shim 用途。

Phase 1 では DB Settings テーブルを作っていないため、現状は環境変数のラッパに留まる。
W4-05(設定画面)実装時に DB から値を読む get_tenant_setting() を追加する想定。
"""

import os
from typing import overload

from app.settings import settings


@overload
def get_env(key: str, *, default: str) -> str: ...
@overload
def get_env(key: str, *, default: None = None) -> str | None: ...
def get_env(key: str, *, default: str | None = None) -> str | None:
    """環境変数を読む。プレフィックスなしのキーをそのまま OS env から取得。"""
    return os.environ.get(key, default)


def get_app_setting(name: str) -> object:
    """Pydantic Settings から属性を引く。テスト時の monkeypatch で書き換え可能。"""
    return getattr(settings, name)


def is_production() -> bool:
    return settings.env == "production"
