import pytest

from kp.config import Settings
from kp.deps import get_container
from kp.infrastructure.llm import LLMClient, provider_presets
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
    # Ensure allowlist includes the desktop Ollama URL used in hybrid profile.
    c.settings.llm_allowed_base_urls = (
        "http://127.0.0.1:11434/v1,http://localhost:11434/v1,"
        "http://host.docker.internal:11434/v1"
    )
    c.llm.apply_config("OLLAMA", "http://host.docker.internal:11434/v1", "qwen2.5:0.5b")
    cfg = c.llm.get_config()
    assert cfg.provider == "OLLAMA"
    assert "11434" in cfg.base_url
    assert "host.docker.internal" in cfg.base_url
    c.llm.apply_config("MOCK")
    assert c.llm.get_config().provider == "MOCK"


def test_ollama_url_model_from_settings_not_code():
    settings = Settings(
        llm_provider="OLLAMA",
        openai_base_url="http://ollama.example:11434/v1",
        llm_model="custom-model:tag",
    )
    client = LLMClient(settings)
    cfg = client.get_config()
    assert cfg.base_url == "http://ollama.example:11434/v1"
    assert cfg.model == "custom-model:tag"
    presets = provider_presets(settings)
    assert presets["OLLAMA"]["base_url"] == settings.openai_base_url
    assert presets["OLLAMA"]["model"] == settings.llm_model
    client.apply_config("OLLAMA")
    assert client.get_config().base_url == settings.openai_base_url
    assert client.get_config().model == settings.llm_model
