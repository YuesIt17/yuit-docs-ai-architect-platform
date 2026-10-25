"""Application DI container — wires infrastructure, repositories, and the agent."""

from __future__ import annotations

from functools import lru_cache

from kp.agent.graph import KnowledgeAgent
from kp.config import Settings, get_settings
from kp.infrastructure.cache import build_semantic_cache
from kp.infrastructure.embeddings import EmbeddingService
from kp.infrastructure.llm import LLMClient
from kp.infrastructure.neo4j_graph import Neo4jGraphRepository
from kp.infrastructure.object_store import ObjectStore
from kp.infrastructure.qdrant_vectors import QdrantVectorRepository
from kp.infrastructure.vision import VisionService
from kp.repositories.hybrid_store import HybridKnowledgeStore
from kp.repositories.memory_store import MemoryKnowledgeStore


class AppContainer:
    """Singleton-ish wiring for FastAPI dependencies and pipelines."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = EmbeddingService(settings)
        memory = MemoryKnowledgeStore(self.embeddings)
        neo4j = None
        qdrant = None
        use_live = settings.store_backend == "live"
        if use_live:
            neo4j = Neo4jGraphRepository(settings)
            qdrant = QdrantVectorRepository(settings)
        self.store = HybridKnowledgeStore(
            memory,
            neo4j=neo4j,
            qdrant=qdrant,
            use_live=use_live,
            strict_live=settings.store_strict_live,
            enable_graph_resolve=settings.enable_graph_resolve,
        )
        self.object_store = ObjectStore(settings)
        self.llm = LLMClient(settings)
        self.vision = VisionService(settings)
        self.cache = build_semantic_cache(settings, self.embeddings)
        self.agent = KnowledgeAgent(self.store, self.llm)
        self._seeded = False


@lru_cache
def get_container() -> AppContainer:
    return AppContainer(get_settings())
