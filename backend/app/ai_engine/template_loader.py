"""プロンプトテンプレートを Markdown + Jinja2 で読み込み、変数差し込みする。

ファイル本体は ai_engine/prompts/<use_case>.md(Source of Truth)。
DB の prompt_templates はパス・バージョンの参照のみ。
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(PROMPTS_DIR),
        autoescape=select_autoescape(disabled_extensions=("md", "txt")),
        undefined=StrictUndefined,  # 未定義変数は ERROR にする
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(template_name: str, context: dict[str, Any]) -> str:
    """プロンプトテンプレートを変数差し込みしてレンダリング。

    template_name: 'monthly_report.md' のようなファイル名(prompts/ からの相対)
    """
    tmpl = _env().get_template(template_name)
    return tmpl.render(**context)
