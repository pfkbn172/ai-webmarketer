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
    """keyword を上から順に各クラスタの aliases と部分一致でマッチさせ、
    最初にマッチしたクラスタを返す。どれにも該当しなければ UNCLASSIFIED。
    """
    norm = normalize(keyword)
    if not norm:
        return _unclassified()

    for cluster in get_clusters():
        for alias in cluster.aliases:
            if alias and alias in norm:
                return cluster
    return _unclassified()


@lru_cache(maxsize=1)
def _unclassified() -> Cluster:
    return Cluster(
        cluster_id=UNCLASSIFIED,
        label="未分類",
        aliases=(),
        is_geographic=False,
        intent=None,
    )
