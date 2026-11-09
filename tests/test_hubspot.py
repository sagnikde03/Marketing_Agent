import unittest
from pathlib import Path
from app.connectors.hubspot import hubspot_connector, DEMO_DEAL
from app.core.config import settings


class TestHubSpotConnector(unittest.TestCase):
    def test_get_deals_offline_returns_demo(self):
        # In offline mode without token, get_deals returns demo deal
        deals = hubspot_connector.get_deals(limit=5)
        self.assertGreaterEqual(len(deals), 1)
        self.assertEqual(deals[0]["id"], DEMO_DEAL["id"])

    def test_get_deal_detail_demo(self):
        deal = hubspot_connector.get_deal_detail("sample-deal")
        self.assertEqual(deal.id, "sample-deal")
        self.assertEqual(deal.name, DEMO_DEAL["properties"]["dealname"])
        self.assertIsNotNone(deal.company)
        self.assertEqual(deal.company.name, "Acme Corporation")
        self.assertEqual(len(deal.contacts), 4)
        self.assertEqual(len(deal.engagements), 3)

    def test_seed_sample_deal(self):
        deal = hubspot_connector.seed_sample_deal()
        self.assertIsNotNone(deal)
        lake_dir = settings.raw_lake_dir / "deals"
        self.assertTrue(lake_dir.exists())


if __name__ == "__main__":
    unittest.main()

