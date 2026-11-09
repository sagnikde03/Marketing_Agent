from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Any, Optional
from app.core.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_dim = 384  # Matches FastEmbed BAAI/bge-small-en-v1.5 and 384-dim normalized embeddings
        self.is_in_memory: bool = False

    def connect(self) -> bool:
        try:
            # Try connecting to external Qdrant container/server
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=2.0,
                check_compatibility=False
            )
            self.client.get_collections()
            self._ensure_collection()
            self.is_in_memory = False
            logger.info("Connected to Qdrant server.")
            return True
        except Exception as e:
            logger.warning(f"Qdrant server not reachable ({e}). Falling back to local in-memory vector storage.")
            try:
                self.client = QdrantClient(":memory:")
                self._ensure_collection()
                self.is_in_memory = True
                return True
            except Exception as mem_err:
                logger.error(f"In-memory Qdrant init failed: {mem_err}")
                self.client = None
                self.is_in_memory = False
                return False

    def _ensure_collection(self):
        if not self.client:
            return
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_dim, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.debug(f"Collection check/create notice: {e}")

    def upsert_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        if not self.client:
            self.connect()

        if not self.client or not chunks or not embeddings:
            return

        points = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(chunk.get("id") or uuid.uuid4())
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
            
            # Ensure payload is JSON-serializable
            payload = {}
            for k, v in chunk.items():
                if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
                    payload[k] = v
                else:
                    payload[k] = str(v)

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            )

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as e:
            logger.error(f"Failed to upsert points into Qdrant: {e}")

    def search_similar(
        self,
        query_embedding: List[float],
        deal_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        if not self.client:
            self.connect()
        if not self.client:
            return []

        query_filter = None
        if deal_id:
            query_filter = Filter(
                must=[FieldCondition(key="deal_id", match=MatchValue(value=deal_id))]
            )

        # Support both qdrant-client search and query_points
        try:
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_embedding,
                    query_filter=query_filter,
                    limit=limit
                )
                points = getattr(response, "points", response)
                return [{"payload": getattr(p, "payload", {}), "score": getattr(p, "score", 0.0), "id": str(getattr(p, "id", ""))} for p in points]
            else:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    query_filter=query_filter,
                    limit=limit
                )
                return [{"payload": r.payload, "score": r.score, "id": str(r.id)} for r in results]
        except Exception as e:
            # Fallback to search if query_points failed
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    query_filter=query_filter,
                    limit=limit
                )
                return [{"payload": r.payload, "score": r.score, "id": str(r.id)} for r in results]
            except Exception as search_err:
                logger.error(f"Error querying vector DB: {search_err}")
                return []

    def get_deal_chunks(self, deal_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.client:
            self.connect()
        if not self.client:
            return []

        try:
            query_filter = Filter(
                must=[FieldCondition(key="deal_id", match=MatchValue(value=deal_id))]
            )
            records, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=limit,
                with_payload=True
            )
            return [r.payload for r in records if r.payload]
        except Exception as e:
            logger.debug(f"Could not scroll deal chunks: {e}")
            return []


vector_store = QdrantVectorStore()
