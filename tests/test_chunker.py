import unittest
from app.etl.chunker import smart_chunker
from app.models.schemas import DealModel, CompanyModel, ContactModel, EngagementModel


class TestSmartChunker(unittest.TestCase):
    def setUp(self):
        self.deal = DealModel(
            id="deal-test-1",
            name="Test Deal",
            amount=50000.0,
            stage="discovery",
            pipeline="default",
            close_date="2026-12-31",
            company=CompanyModel(
                id="comp-1",
                name="TestCo",
                domain="test.co",
                industry="Software",
                number_of_employees="100",
                annual_revenue="10000000"
            ),
            contacts=[
                ContactModel(
                    id="c-1",
                    first_name="Jane",
                    last_name="Doe",
                    email="jane@test.co",
                    job_title="VP Engineering"
                )
            ],
            engagements=[
                EngagementModel(
                    id="eng-1",
                    type="NOTE",
                    body="<p>Jane indicated budget is allocated for Q4. Need SOC2 report.</p>",
                    created_at="2026-08-01T10:00:00Z",
                    author="rep_1"
                ),
                EngagementModel(
                    id="eng-2",
                    type="CALL",
                    body="Speaker 1 (Rep): How is evaluation going?\n\nSpeaker 2 (Jane): We need VPC peering.",
                    created_at="2026-08-05T15:00:00Z",
                    author="rep_1"
                )
            ]
        )

    def test_chunk_deal_creates_overview_and_engagements(self):
        chunks = smart_chunker.chunk_deal(self.deal)
        self.assertGreaterEqual(len(chunks), 3)

        overview_chunk = chunks[0]
        self.assertEqual(overview_chunk.id, "deal-test-1_overview")
        self.assertEqual(overview_chunk.source_type, "CRM_RECORD")
        self.assertIn("Test Deal", overview_chunk.content)
        self.assertIn("$50,000.00", overview_chunk.content)
        self.assertIn("TestCo", overview_chunk.content)
        self.assertIn("Jane Doe", overview_chunk.content)

    def test_clean_html_preserves_newlines(self):
        html_input = "<p>First paragraph.</p><br><div>Second paragraph with <b>bold</b> text.</div>"
        cleaned = smart_chunker._clean_html(html_input)
        self.assertIn("First paragraph.", cleaned)
        self.assertIn("Second paragraph with bold text.", cleaned)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("</div>", cleaned)

    def test_chunk_speaker_turns(self):
        transcript = "Speaker 1 (Alex): Hello.\n\nSpeaker 2 (Sarah): Hi Alex, let's discuss pricing."
        turns = smart_chunker._chunk_speaker_turns(transcript)
        self.assertEqual(len(turns), 2)
        self.assertIn("Speaker 1", turns[0])
        self.assertIn("Speaker 2", turns[1])


if __name__ == "__main__":
    unittest.main()

