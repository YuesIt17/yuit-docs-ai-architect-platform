import pytest

from app.deps import get_container
from pipelines.seed_all import seed_store


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


@pytest.mark.asyncio
async def test_probe_mock(seeded):
    c = seeded
    probe = await c.llm.probe()
    assert probe["provider"] == "MOCK"
    assert probe["reachable"] is True


@pytest.mark.asyncio
async def test_switch_provider_runtime(seeded):
    c = seeded
    c.llm.apply_config("OLLAMA", "http://host.docker.internal:11434/v1", "qwen2.5:0.5b")
    cfg = c.llm.get_config()
    assert cfg.provider == "OLLAMA"
    assert "11434" in cfg.base_url
    assert "host.docker.internal" in cfg.base_url
    c.llm.apply_config("MOCK")
    assert c.llm.get_config().provider == "MOCK"
