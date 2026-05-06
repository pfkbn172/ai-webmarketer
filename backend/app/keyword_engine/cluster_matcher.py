"""クラスタ辞書のロードと keyword→cluster の割当て。"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.keyword_engine.normalizer import normalize


CLUSTERS_PATH = Path(__file__).parent / "clusters.yaml"

UNCLASSIFIED = "unclassified"


@dataclass(frozen=True, slots=True)
class Cluster:
    cluster_id: str
    label: str
    aliases: tuple[str, ...]  # 正規化済み
    is_geographic: bool
    intent: str | None


def _load_clusters(path: Path = CLUSTERS_PATH) -> list[Cluster]:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[Cluster] = []
    for cluster_id, conf in (raw.get("clusters") or {}).items():
        aliases_raw = conf.get("aliases") or []
        aliases_norm = tuple(normalize(a) for a in aliases_raw if a)
        out.append(
            Cluster(
                cluster_id=cluster_id,
                label=conf.get("label") or cluster_id,
                aliases=aliases_norm,
                is_geographic=bool(conf.get("is_geographic", False)),
                intent=conf.get("intent"),
            )
        )
    return out


@lru_cache(maxsize=1)
def get_clusters() -> tuple[Cluster, ...]:
    return tuple(_load_clusters())


def classify(keyword: str) -> Cluster:
    """先頭マッチを返す互換 API。新規コードは classify_all() を使うこと。"""
    matches = classify_all(keyword)
    return matches[0] if matches else _unclassified()


# 1キーワードに付与する最大クラスタ数(計画書 §3 マルチクラスタ対応)。
MAX_CLUSTERS_PER_KEYWORD = 3


def classify_all(keyword: str) -> list[Cluster]:
    """keyword に該当する全クラスタを最大 MAX_CLUSTERS_PER_KEYWORD 個まで返す。

    一致順は clusters.yaml の登場順(地域系優先 → 業者探索 → DX/AI/RPA 等 → 補助金 → ツール)。
    どこにも該当しなければ UNCLASSIFIED 1つだけ返す。
    """
    norm = normalize(keyword)
    if not norm:
        return [_unclassified()]

    matched: list[Cluster] = []
    for cluster in get_clusters():
        for alias in cluster.aliases:
            if alias and alias in norm:
                matched.append(cluster)
                break
        if len(matched) >= MAX_CLUSTERS_PER_KEYWORD:
            break
    return matched if matched else [_unclassified()]


@lru_cache(maxsize=1)
def _unclassified() -> Cluster:
    return Cluster(
        cluster_id=UNCLASSIFIED,
        label="未分類",
        aliases=(),
        is_geographic=False,
        intent=None,
    )
