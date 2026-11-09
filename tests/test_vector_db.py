import unittest
from app.core.vector_db import QdrantVectorStore


class TestVectorDB(unittest.TestCase):
    def setUp(self):
        self.store = QdrantVectorStore()
        # Force in-memory client
        from qdrant_client import QdrantClient
        self.store.client = QdrantClient(":memory:")
        self.store.is_in_memory = True
        self.store._ensure_collection()

    def test_upsert_and_search(self):
        chunks = [
            {"id": "chunk-1", "deal_id": "d-1", "source_type": "NOTE", "content": "Budget approved by CFO."},
            {"id": "chunk-2", "deal_id": "d-2", "source_type": "CALL", "content": "Competitor Splunk mentioned."}
        ]
        # Dummy 384-dimensional unit vectors
        emb1 = [0.0] * 384
        emb1[0] = 1.0
        emb2 = [0.0] * 384
        emb2[1] = 1.0

        self.store.upsert_chunks(chunks, [emb1, emb2])

        # Query similar to emb1
        results = self.store.search_similar(emb1, deal_id="d-1", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["payload"]["id"], "chunk-1")

        # Query filtered by deal_id d-2
        results_d2 = self.store.search_similar(emb1, deal_id="d-2", limit=5)
        self.assertEqual(len(results_d2), 0)

    def test_get_deal_chunks(self):
        chunks = [
            {"id": "scroll-1", "deal_id": "deal-scroll", "content": "Content 1"},
            {"id": "scroll-2", "deal_id": "deal-scroll", "content": "Content 2"},
        ]
        embs = [[0.1] * 384, [0.2] * 384]
        self.store.upsert_chunks(chunks, embs)

        retrieved = self.store.get_deal_chunks("deal-scroll")
        self.assertEqual(len(retrieved), 2)


if __name__ == "__main__":
    unittest.main()
