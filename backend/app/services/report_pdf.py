"""月次レポートを PDF に変換する。

WeasyPrint を使い、reports.summary_html を組み込んだ簡易テンプレートで出力。
日本語フォントは OS の Noto Sans CJK 等が自動選択される。
"""

from io import BytesIO

from weasyprint import HTML

from app.utils.logger import get_logger

log = get_logger(__name__)


_BASE_CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Noto Sans CJK JP", "Noto Sans JP", "IPAGothic", "Hiragino Sans",
              "Yu Gothic", "Meiryo", sans-serif;
       font-size: 10.5pt; color: #222; line-height: 1.6; }
h1 { font-size: 18pt; border-bottom: 2px solid #444; padding-bottom: 6px; }
h2 { font-size: 14pt; margin-top: 18pt; border-left: 4px solid #4f46e5;
     padding-left: 8px; }
h3 { font-size: 11.5pt; margin-top: 12pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
th, td { border: 1px solid #ddd; padding: 4pt 6pt; text-align: left; }
th { background: #f3f4f6; }
.meta { color: #555; font-size: 9pt; }
"""


def render_report_to_pdf(*, period: str, title: str, summary_html: str | None) -> bytes:
    """report レコード相当の入力から PDF バイト列を返す。"""
    html_str = (
        f"<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<style>{_BASE_CSS}</style></head><body>"
        f"<h1>{title}</h1>"
        f"<p class='meta'>対象期間: {period}</p>"
        f"{summary_html or '<p>(本文なし)</p>'}"
        f"</body></html>"
    )
    buf = BytesIO()
    HTML(string=html_str).write_pdf(buf)
    return buf.getvalue()
