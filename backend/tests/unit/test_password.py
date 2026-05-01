from app.auth.password import hash_password, needs_rehash, verify_password


def test_hash_then_verify_succeeds() -> None:
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h) is True


def test_verify_fails_for_wrong_password() -> None:
    h = hash_password("real")
    assert verify_password("fake", h) is False


def test_hash_is_unique_per_call() -> None:
    """同じ入力でも salt が異なるためハッシュ文字列は毎回違う。"""
    a = hash_password("x")
    b = hash_password("x")
    assert a != b


def test_needs_rehash_is_false_for_fresh_hash() -> None:
    h = hash_password("x")
    assert needs_rehash(h) is False
