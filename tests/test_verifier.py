import unittest
from app.engine.verifier import verifier
from app.models.schemas import MeddicSection, TextChunk


class TestVerificationAgent(unittest.TestCase):
    def setUp(self):
        self.evidence_chunks = [
            TextChunk(
                id="ev-1",
                deal_id="d-1",
                source_type="CALL_TRANSCRIPT",
                source_id="call-1",
                speaker_or_author="rep_alex",
                timestamp="2026-07-28T16:00:00Z",
                content="Elena Reyes (CFO) signed off on exploratory budget cap of $200k ARR."
            ),
            TextChunk(
                id="ev-2",
                deal_id="d-1",
                source_type="NOTE_RECORD",
                source_id="note-1",
                speaker_or_author="rep_alex",
                timestamp="2026-07-15T14:30:00Z",
                content="Datadog retention costs are escalating uncontrollably at $45k/mo."
            )
        ]

    def test_verify_grounded_claim(self):
        section = MeddicSection(
            title="💰 Economic Buyer",
            key_findings=["Elena Reyes (CFO) has signed off on $200k budget."],
            strategy_recommendation="Confirm threshold."
        )
        verified = verifier.verify_section(section, self.evidence_chunks)
        self.assertEqual(len(verified.claims), 1)
        self.assertEqual(verified.claims[0].status, "GROUNDED")
        self.assertIn("Source:", verified.claims[0].source_citation)

    def test_verify_unsupported_claim(self):
        section = MeddicSection(
            title="💰 Economic Buyer",
            key_findings=["Missing Signal: Unknown decision maker."],
            strategy_recommendation="Discover."
        )
        verified = verifier.verify_section(section, self.evidence_chunks)
        self.assertEqual(len(verified.claims), 1)
        self.assertEqual(verified.claims[0].status, "UNSUPPORTED")
        self.assertIsNone(verified.claims[0].source_citation)


if __name__ == "__main__":
    unittest.main()
