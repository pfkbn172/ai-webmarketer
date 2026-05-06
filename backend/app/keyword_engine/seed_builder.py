"""business_context からサジェスト収集用シードキーワードを生成する。

設計指針(計画書 §1.2 / §3 / Phase 1-2):
- 1テナントあたり 20〜40 本程度。多すぎると Google/Bing への負荷が高く、少なすぎると派生が薄い。
- 提供サービス × 修飾(地域・業界主語) を直積する。
- 拠点地域は採用、拡大目標地域は半分だけ採用(全部やると爆発する)。
- DX/AI/業務効率化等のクラスタ主軸ワードを単独でも投入する(派生語の山を取りに行く)。
- 競合観察用クエリ(「中小企業 DX 大阪」など)も意図的に含める。
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Seed:
    text: str
    source_hint: str  # 'offering' | 'offering_x_geo' | 'cluster' | 'subject_x_cluster'


# 主軸クラスタの単独シード(派生語が一番多く取れるので必須)
PRIMARY_CLUSTER_SEEDS = [
    "中小企業 DX",
    "中小企業 AI",
    "中小企業 IT",
    "業務効率化",
    "業務自動化",
    "RPA",
    "生成AI",
    "DX とは",
    "業務改善",
    "デジタル化 中小企業",
    "IT導入補助金",
]


# 業者探索文脈で重要(購買意図のシード)
VENDOR_INTENT_TEMPLATES = [
    "{geo} DX コンサル",
    "{geo} IT サポート 中小企業",
    "{geo} DX 支援",
]


# 業種主語(target_customer から拾えなければデフォルト)
DEFAULT_SUBJECTS = ["中小企業", "零細企業", "個人事業主"]


# 拡大地域は使用率を絞る(計画書: 全部使うとシード爆発)
EXPANSION_RATIO = 0.5
MAX_TOTAL_SEEDS = 40


def build_seeds(business_context: dict[str, Any]) -> list[Seed]:
    """business_context dict からシードリストを返す。重複は排除済。"""
    bc = business_context or {}

    offerings: list[str] = list(bc.get("primary_offerings") or [])
    base_geos: list[str] = list(bc.get("geographic_base") or [])
    expand_geos: list[str] = list(bc.get("geographic_expansion") or [])

    seen: set[str] = set()
    out: list[Seed] = []

    def _add(text: str, hint: str) -> None:
        t = (text or "").strip()
        if not t:
            return
        # 重複は完全一致(正規化は collector 側で行う)
        if t in seen:
            return
        seen.add(t)
        out.append(Seed(text=t, source_hint=hint))

    # 1) クラスタ主軸シード(派生語の確保)
    for s in PRIMARY_CLUSTER_SEEDS:
        _add(s, "cluster")

    # 2) 提供サービス単独
    for off in offerings:
        # offerings は長文気味なので、コア語(2語以内)に圧縮するためそのまま投げる
        _add(off, "offering")

    # 3) 提供サービス × 拠点地域(直積)
    for off in offerings:
        for geo in base_geos:
            _add(f"{geo} {_compact_offering(off)}", "offering_x_geo")

    # 4) 拡大地域は半分だけ採用(EXPANSION_RATIO)
    expand_pick = expand_geos[: max(1, int(len(expand_geos) * EXPANSION_RATIO))]
    for off in offerings[:2]:  # 拡大はサービス上位2つだけ
        for geo in expand_pick:
            _add(f"{geo} {_compact_offering(off)}", "offering_x_geo")

    # 5) 業者探索文脈(地域 × 購買意図テンプレ)
    geos_for_vendor = base_geos[:3]  # 拠点地域 上位3つ
    for tmpl in VENDOR_INTENT_TEMPLATES:
        for geo in geos_for_vendor:
            _add(tmpl.format(geo=geo), "vendor_intent")

    # 6) 主語 × クラスタ(中小企業 DX 等は既にPRIMARYに含むので、零細/個人事業主バリエーション)
    for subj in DEFAULT_SUBJECTS[1:]:
        for cluster in ["DX", "AI", "業務効率化"]:
            _add(f"{subj} {cluster}", "subject_x_cluster")

    return out[:MAX_TOTAL_SEEDS]


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

# 提供サービスは長文なので、よく出る尾語を落としてコア化する。
# 例: "中小企業向け IT/DX サポート" -> "IT DX サポート"
_COMPACT_REPLACE = [
    ("中小企業向け", ""),
    ("/", " "),
    ("　", " "),
]


def _compact_offering(off: str) -> str:
    s = off
    for a, b in _COMPACT_REPLACE:
        s = s.replace(a, b)
    s = " ".join(s.split())  # 連続空白圧縮
    return s.strip()
