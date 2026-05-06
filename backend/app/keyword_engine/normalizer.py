"""キーワード正規化(全半角統一・小文字化・空白整理)。"""

import re
import unicodedata


_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """マッチング用に正規化したキーワードを返す。

    - NFKC で全角英数記号→半角、半角カナ→全角カナを統一
    - 小文字化
    - 連続空白を1つにまとめ、両端を strip
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.lower()
    s = _WS_RE.sub(" ", s).strip()
    return s
