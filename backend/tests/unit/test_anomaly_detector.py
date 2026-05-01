from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.anomaly_detector import detect


async def test_detects_rank_drop() -> None:
    today = date.today()
    last_week = today - timedelta(days=3)
    prev_week = today - timedelta(days=10)
    rows = [
        MagicMock(query_text="q1", date=prev_week, position=3.0),
        MagicMock(query_text="q1", date=last_week, position=20.0),
    ]

    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=rows)))

    # 引用ログは空にする
    async def execute_side(*args, **kwargs):
        # 1 回目は GSC 行、2 回目は CitationLog 行
        nonlocal calls
        calls += 1
        if calls == 1:
            return MagicMock(all=MagicMock(return_value=rows))
        return MagicMock(all=MagicMock(return_value=[]))

    calls = 0
    session.execute = AsyncMock(side_effect=execute_side)

    import uuid as _uuid
    anomalies = await detect(session, _uuid.uuid4())
    kinds = [a.kind for a in anomalies]
    assert "rank_drop" in kinds


async def test_no_anomaly_when_no_data() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    import uuid as _uuid
    anomalies = await detect(session, _uuid.uuid4())
    assert anomalies == []
