"""LLM レスポンスから JSON を頑健に抽出するためのユーティリティ。

Gemini / Claude / OpenAI は response_format=json を指定しても、
- ```json ... ``` コードフェンスで囲む
- 前置きや後書き(「ここに JSON を返します:」等)を入れる
- max_tokens で末尾が切れる
といった逸脱があり得る。json.loads そのままだと壊れるので、
構文を意識して抽出 + 末尾切れの救済まで行う。
"""

import json
from typing import Any

from app.utils.logger import get_logger

log = get_logger(__name__)


def _scan_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """text[start] が open_ch のとき、対応する close_ch のインデックスを返す。
    バランスが取れる前に文字列が終わったら -1 を返す。文字列リテラル内の括弧は無視。
    """
    if start >= len(text) or text[start] != open_ch:
        return -1
    depth = 0
    i = start
    in_str = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _truncate_recover(snippet: str, expect_close: str) -> str:
    """末尾切れの snippet を、有効な JSON にするために補完する。

    最終的に snippet[0] の対応括弧を expect_close で閉じる。
    途中で string が開きっぱなしなら "" で閉じ、配列・オブジェクトが
    開きっぱなしならそれぞれ ] / } で閉じる。
    """
    in_str = False
    escape = False
    stack: list[str] = []
    last_safe = 0  # 値の区切り(,) の直後の安全な位置
    for i, ch in enumerate(snippet):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
                # 文字列が閉じた直後を安全位置として記録(後でここまで切り戻す)
                last_safe = i + 1
        else:
            if ch == '"':
                in_str = True
            elif ch in ("{", "["):
                stack.append("}" if ch == "{" else "]")
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()
                last_safe = i + 1
            elif ch == ",":
                last_safe = i  # カンマ自体は最後に来てはダメなので位置 i
    # 末尾で string がまだ開いていたら、そこまで戻す
    if in_str:
        snippet = snippet[:last_safe]
    else:
        snippet = snippet[: last_safe if last_safe > 0 else len(snippet)]
    # 末尾の余分なカンマを除去
    snippet = snippet.rstrip().rstrip(",")
    # スタックを逆順に閉じる
    # スタックを再計算(snippet を切り戻したので)
    stack = []
    in_str = False
    escape = False
    for ch in snippet:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in ("{", "["):
                stack.append("}" if ch == "{" else "]")
            elif ch in ("}", "]") and stack and stack[-1] == ch:
                stack.pop()
    while stack:
        snippet += stack.pop()
    # 念のため期待する閉じで終わっていなければ追加(通常は上で完了している)
    if not snippet.endswith(expect_close):
        snippet += expect_close
    return snippet


def parse_json_object(text: str, *, log_label: str = "llm_json_object") -> dict[str, Any]:
    """LLM レスポンスから最初の { ... } を抽出してパース。

    1. 最初の '{' を探す
    2. balance 走査で対応する '}' を見つける(切れていなければそれが完成形)
    3. 完成形をパース。失敗 or 末尾が切れていれば truncation 救済を試す
    """
    if not text:
        log.warning(f"{log_label}_empty")
        return {}
    start = text.find("{")
    if start == -1:
        log.warning(f"{log_label}_no_object", raw=text[:500])
        return {}

    end = _scan_balanced(text, start, "{", "}")
    if end != -1:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 末尾が切れているケース: start から最後までをそのまま使い、補完を試す
    snippet = text[start:]
    patched = _truncate_recover(snippet, "}")
    try:
        parsed = json.loads(patched)
        if isinstance(parsed, dict):
            log.info(f"{log_label}_partial_recovered", original_len=len(snippet), patched_len=len(patched))
            return parsed
    except json.JSONDecodeError as e:
        log.warning(
            f"{log_label}_invalid",
            err=str(e),
            raw_head=text[:500],
            raw_tail=text[-500:] if len(text) > 500 else "",
            patched_tail=patched[-300:] if patched else "",
        )
    return {}


def parse_json_array(text: str, *, log_label: str = "llm_json_array") -> list[dict]:
    """LLM レスポンスから最初の [ ... ] を抽出してパース。"""
    if not text:
        return []
    start = text.find("[")
    if start == -1:
        log.warning(f"{log_label}_no_array", raw=text[:500])
        return []

    end = _scan_balanced(text, start, "[", "]")
    if end != -1:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    snippet = text[start:]
    patched = _truncate_recover(snippet, "]")
    try:
        parsed = json.loads(patched)
        if isinstance(parsed, list):
            log.info(f"{log_label}_partial_recovered", n=len(parsed))
            return parsed
    except json.JSONDecodeError:
        log.warning(f"{log_label}_invalid", raw_head=text[:500], raw_tail=text[-500:] if len(text) > 500 else "")
    return []
