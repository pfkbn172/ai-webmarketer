import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.auth import jwt as jwt_mod
from app.auth.jwt import TokenError, decode_token, issue_access_token, issue_refresh_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jwt_mod.settings, "jwt_secret", "test-secret-very-long-xxxxxxxx")
    monkeypatch.setattr(jwt_mod.settings, "jwt_ttl_minutes", 60)
    monkeypatch.setattr(jwt_mod.settings, "jwt_refresh_ttl_days", 14)


def test_issue_and_decode_access_token() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    token, exp = issue_access_token(user_id=uid, role="admin", tenant_id=tid)
    claims = decode_token(token)
    assert claims.user_id == uid
    assert claims.tenant_id == tid
    assert claims.role == "admin"
    assert claims.token_type == "access"
    assert claims.expires_at > datetime.now(UTC)


def test_issue_and_decode_refresh_token() -> None:
    uid = uuid.uuid4()
    token, _ = issue_refresh_token(user_id=uid)
    claims = decode_token(token)
    assert claims.user_id == uid
    assert claims.token_type == "refresh"
    assert claims.tenant_id is None


def test_decode_rejects_invalid_signature() -> None:
    uid = uuid.uuid4()
    token, _ = issue_access_token(user_id=uid, role="client", tenant_id=None)
    # 署名部(最後のセグメント)を完全に書き換える
    head, _, _ = token.rpartition(".")
    tampered = head + ".invalid-signature"
    with pytest.raises(TokenError):
        decode_token(tampered)


def test_decode_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT の exp は秒単位なので、過去時刻にした iat/exp で発行する。"""
    uid = uuid.uuid4()

    # _now を過去にずらして 1 分有効のトークンを作る → 即座に検証すると expired
    fake_now = datetime.now(UTC) - timedelta(hours=2)
    monkeypatch.setattr(jwt_mod, "_now", lambda: fake_now)
    monkeypatch.setattr(jwt_mod.settings, "jwt_ttl_minutes", 1)
    token, _ = issue_access_token(user_id=uid, role="client", tenant_id=None)
    monkeypatch.undo()

    # 念のため少し待って検証(小さな leeway を考慮)
    time.sleep(0.01)
    with pytest.raises(TokenError):
        decode_token(token)


def test_decode_without_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jwt_mod.settings, "jwt_secret", "")
    with pytest.raises(TokenError, match="JWT_SECRET"):
        decode_token("anything")
