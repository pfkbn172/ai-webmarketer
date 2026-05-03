"""anomaly_detector の単体テスト(モック化)。

Phase 2 で複雑化したため、要点だけ確認するスモークレベルテスト。
"""

import uuid as _uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.anomaly_detector import detect


async def test_detects_rank_drop() -> None:
    today = date.today()
    last_week = today - timedelta(days=3)
    prev_week = today - timedelta(days=10)
    gsc_rows = [
        MagicMock(query_text="q1", date=prev_week, position=3.0),
        MagicMock(query_text="q1", date=last_week, position=20.0),
    ]

    seq = [
        gsc_rows,                                # 1) GSC ranking rows
        [],                                      # 2) citation rows for drop comparison
        MagicMock(total=0, self_count=0),        # 3) chronic_zero aggregate
    ]
    calls = {"i": 0}

    async def execute_side(*_a, **_kw):
        i = calls["i"]
        calls["i"] += 1
        r = MagicMock()
        if i < len(seq):
            v = seq[i]
            r.all = MagicMock(return_value=v if isinstance(v, list) else [v])
            r.one = MagicMock(return_value=v)
        else:
            r.all = MagicMock(return_value=[])
            r.one = MagicMock(return_value=MagicMock(total=0, self_count=0))
        return r

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side)
    # tenant 取得 → None(business_context 検査をスキップ)
    scalars_result = MagicMock()
    scalars_result.one_or_none = MagicMock(return_value=None)
    scalars_result.all = MagicMock(return_value=[])
    session.scalars = AsyncMock(return_value=scalars_result)

    anomalies = await detect(session, _uuid.uuid4())
    kinds = [a.kind for a in anomalies]
    assert "rank_drop" in kinds


async def test_no_anomaly_when_no_data() -> None:
    seq = [
        [],                                      # 1) GSC
        [],                                      # 2) citation rows
        MagicMock(total=0, self_count=0),        # 3) chronic_zero
    ]
    calls = {"i": 0}

    async def execute_side(*_a, **_kw):
        i = calls["i"]
        calls["i"] += 1
        r = MagicMock()
        if i < len(seq):
            v = seq[i]
            r.all = MagicMock(return_value=v if isinstance(v, list) else [v])
            r.one = MagicMock(return_value=v)
        else:
            r.all = MagicMock(return_value=[])
            r.one = MagicMock(return_value=MagicMock(total=0, self_count=0))
        return r

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side)
    scalars_result = MagicMock()
    scalars_result.one_or_none = MagicMock(return_value=None)
    scalars_result.all = MagicMock(return_value=[])
    session.scalars = AsyncMock(return_value=scalars_result)

    anomalies = await detect(session, _uuid.uuid4())
    assert anomalies == []
