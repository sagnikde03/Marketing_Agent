import unittest
import math
from app.etl.indexer import vector_indexer
from app.models.schemas import TextChunk


class TestVectorIndexer(unittest.TestCase):
    def test_pseudo_embeddings_dimension_and_normalization(self):
        texts = ["Enterprise Observability Modernization", "SOC2 compliance and VPC peering"]
        embeddings = vector_indexer.get_embeddings(texts)

        self.assertEqual(len(embeddings), 2)
        for emb in embeddings:
            self.assertEqual(len(emb), 384)
            # Check unit length (L2 norm should be approximately 1.0)
            norm = math.sqrt(sum(x * x for x in emb))
            self.assertAlmostEqual(norm, 1.0, places=3)

    def test_embed_query(self):
        query = "CFO budget sign-off"
        emb = vector_indexer.embed_query(query)
        self.assertEqual(len(emb), 384)
        norm = math.sqrt(sum(x * x for x in emb))
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_index_deal_chunks(self):
        chunks = [
            TextChunk(
                id="idx-chunk-1",
                deal_id="deal-idx",
                source_type="NOTE",
                source_id="note-idx-1",
                content="Indexing test content."
            )
        ]
        # Should not raise exception
        vector_indexer.index_deal_chunks(chunks)


if __name__ == "__main__":
    unittest.main()

