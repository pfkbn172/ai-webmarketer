"""LLM レスポンスから JSON を頑健に抽出するためのユーティリティ。

Gemini / Claude / OpenAI は response_format=json を指定しても、
- ```json ... ``` コードフェンスで囲む
- 前置きや後書き(「ここに JSON を返します:」等)を入れる
- max_tokens で末尾が切れる
といった逸脱があり得る。json.loads そのままだと壊れるので、
頭の '{' / '[' から末尾の '}' / ']' までを切り出してから
パースする。失敗時はログだけ残してデフォルト値を返す。
"""

import json
from typing import Any

from app.utils.logger import get_logger

log = get_logger(__name__)


def parse_json_object(text: str, *, log_label: str = "llm_json_object") -> dict[str, Any]:
    """LLM レスポンスから最初の { ... } を抽出してパース。失敗したら空 dict。"""
    if not text:
        log.warning(f"{log_label}_empty")
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        log.warning(f"{log_label}_no_object", raw=text[:500])
        return {}
    snippet = text[start : end + 1]
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        # 末尾が途切れた場合の救済: 最後の "," 位置で閉じ直す
        for cut_at in (snippet.rfind("},"), snippet.rfind('",')):
            if cut_at > 0:
                patched = snippet[: cut_at + 1].rstrip(",") + "}"
                try:
                    parsed = json.loads(patched)
                    if isinstance(parsed, dict):
                        log.info(f"{log_label}_partial_recovered")
                        return parsed
                except json.JSONDecodeError:
                    continue
    log.warning(f"{log_label}_invalid", raw=text[:1000])
    return {}


def parse_json_array(text: str, *, log_label: str = "llm_json_array") -> list[dict]:
    """LLM レスポンスから最初の [ ... ] を抽出してパース。失敗したら空リスト。"""
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        log.warning(f"{log_label}_no_array", raw=text[:500])
        return []
    snippet = text[start : end + 1]
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        last_close = snippet.rfind("},")
        if last_close > 0:
            patched = snippet[: last_close + 1] + "]"
            try:
                parsed = json.loads(patched)
                if isinstance(parsed, list):
                    log.info(f"{log_label}_partial_recovered", n=len(parsed))
                    return parsed
            except json.JSONDecodeError:
                pass
    log.warning(f"{log_label}_invalid", raw=text[:1000])
    return []
