from typing import List, Optional
import math
import logging
from app.core.config import settings
from app.core.vector_db import vector_store
from app.models.schemas import TextChunk

logger = logging.getLogger(__name__)


class VectorIndexer:
    """Vector Indexer generating 384-dimensional dense vectors with tiered fallback."""

    def __init__(self):
        self._hf_embedder = None
        self._openai_client = None

    def _get_openai_client(self):
        if self._openai_client is None and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.debug(f"OpenAI client init notice: {e}")
        return self._openai_client

    def _get_fastembed(self):
        if self._hf_embedder is None:
            try:
                from fastembed import TextEmbedding
                logger.info("Initializing free local HuggingFace embedding model: BAAI/bge-small-en-v1.5")
                self._hf_embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            except Exception as e:
                logger.debug(f"FastEmbed not available ({e}).")
        return self._hf_embedder

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # 1. Tier 1: Try OpenAI Embeddings if API key is provided
        client = self._get_openai_client()
        if client:
            try:
                # text-embedding-3-small supports reducing dimensions to 384
                response = client.embeddings.create(
                    input=texts,
                    model=settings.EMBEDDING_MODEL,
                    dimensions=384
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.debug(f"OpenAI embedding call failed or rate-limited ({e}). Trying FastEmbed / local fallback.")

        # 2. Tier 2: Try FastEmbed (Local BAAI/bge-small-en-v1.5, 384 dims)
        embedder = self._get_fastembed()
        if embedder:
            try:
                embeddings_gen = embedder.embed(texts)
                return [emb.tolist() for emb in embeddings_gen]
            except Exception as e:
                logger.debug(f"FastEmbed embedding generation failed: {e}")

        # 3. Tier 3: Deterministic feature-hash pseudo-embedding (384-dim normalized vector)
        # Guarantees zero crashes even completely offline without any ML weights installed
        return [self._generate_pseudo_embedding(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        """Generates embedding for a single search query."""
        results = self.get_embeddings([query])
        return results[0] if results else [0.0] * 384

    def _generate_pseudo_embedding(self, text: str) -> List[float]:
        vec = [0.0] * 384
        cleaned = text.lower().strip()
        words = cleaned.split()
        
        # Word hashing
        for w_idx, word in enumerate(words[:150]):
            h = 0
            for char in word:
                h = (h * 31 + ord(char)) & 0xFFFFFFFF
            pos = h % 384
            weight = 1.0 / (1.0 + math.log1p(w_idx + 1))
            vec[pos] += weight

        # Char trigram hashing for vocabulary generalization
        for i in range(len(cleaned) - 2):
            trigram = cleaned[i:i+3]
            h = (ord(trigram[0]) * 31 * 31 + ord(trigram[1]) * 31 + ord(trigram[2])) & 0xFFFFFFFF
            pos = h % 384
            vec[pos] += 0.25

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def index_deal_chunks(self, chunks: List[TextChunk]):
        if not chunks:
            return

        texts = [c.content for c in chunks]
        embeddings = self.get_embeddings(texts)
        chunk_dicts = [c.model_dump() for c in chunks]
        vector_store.upsert_chunks(chunk_dicts, embeddings)
        logger.info(f"Indexed {len(chunks)} chunks into vector store.")


vector_indexer = VectorIndexer()
