"""Argon2id によるパスワードハッシュ化・検証。

仕様書 9.1 / 設計指針 10.1:
- 平文パスワードは保存しない、ハッシュ化してから DB へ
- 検証時は定数時間比較(argon2-cffi の verify が内部で実装)
- ハッシュには salt とパラメータが埋め込まれるので、別カラムに salt を持つ必要はない

OWASP 推奨パラメータ(2024):
- Argon2id, m=19456 (19 MiB), t=2, p=1
- argon2-cffi のデフォルトは m=65536 (64 MiB), t=3, p=4 で十分強い
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _hasher.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    """ハッシュアルゴリズム/パラメータが古ければ True。ログイン成功時に再ハッシュする運用想定。"""
    return _hasher.check_needs_rehash(hashed)
