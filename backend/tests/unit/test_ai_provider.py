"""AI Provider 抽象レイヤの基本動作を Mock Adapter で検証。"""

from pydantic import BaseModel

from app.ai_engine.providers.mock_adapter import MockAdapter
from app.ai_engine.providers.schemas import ProviderResponse
from app.ai_engine.template_loader import render


async def test_mock_adapter_generate() -> None:
    adapter = MockAdapter(fixed_text="hello mock")
    res = await adapter.generate("system", "user")
    assert isinstance(res, ProviderResponse)
    assert res.text == "hello mock"
    assert res.provider == "mock"
    assert res.usage.total_tokens > 0


async def test_mock_adapter_structured() -> None:
    class Schema(BaseModel):
        name: str
        score: int

    adapter = MockAdapter()
    res = await adapter.generate_structured("s", "u", Schema)
    assert isinstance(res, Schema)
    assert res.name == "mock"
    assert res.score == 0


async def test_mock_adapter_stream() -> None:
    adapter = MockAdapter(fixed_text="alpha beta gamma")
    chunks = []
    async for c in adapter.stream("s", "u"):
        chunks.append(c)
    assert "alpha " in chunks


def test_template_render() -> None:
    out = render(
        "weekly_summary.md",
        {
            "tenant_name": "kiseeeen",
            "kpi_summary": "+10% sessions",
            "anomalies": "none",
            "recent_activities": "1 article published",
        },
    )
    assert "kiseeeen" in out
    assert "+10% sessions" in out
