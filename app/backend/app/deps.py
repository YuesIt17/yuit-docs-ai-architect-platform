from __future__ import annotations

from functools import lru_cache

from app.agent.graph import KnowledgeAgent
from app.config import Settings, get_settings
from app.services.cache import SemanticCache
from app.services.embeddings import EmbeddingService
from app.services.knowledge_store import KnowledgeStore
from app.services.llm import LLMClient
from app.services.object_store import ObjectStore
from app.services.vision import VisionService


class AppContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = EmbeddingService(settings)
        self.store = KnowledgeStore(self.embeddings)
        self.object_store = ObjectStore(settings)
        self.llm = LLMClient(settings)
        self.vision = VisionService(settings)
        self.cache = SemanticCache(settings, self.embeddings)
        self.agent = KnowledgeAgent(self.store, self.llm)
        self._seeded = False


@lru_cache
def get_container() -> AppContainer:
    return AppContainer(get_settings())
