import unittest
from datetime import datetime, timezone

from pipeline import process, similarity


class PipelineTest(unittest.TestCase):
    def test_similarity_prefers_related_model(self):
        related = similarity("Mini Jesus 3D figure", "Mini Jesus figure STL")
        unrelated = similarity("Mini Jesus 3D figure", "Phone holder")
        self.assertGreater(related, unrelated)

    def test_1688_fields_remain_empty_without_match(self):
        payload = {
            "shopee": [{"title": "Mini Jesus 3D", "listed_at": datetime.now(timezone.utc).isoformat(), "url": "https://shopee.example/1", "shop": "a"}],
            "makerworld": [{"title": "Mini Jesus 3D", "url": "https://makerworld.example/1", "license": "CC BY"}],
            "sources_1688": [],
        }
        rows = process(payload)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].settlement_price_cny)
        self.assertIsNone(rows[0].weight_kg)
        self.assertEqual(rows[0].review_status, "待切片/补货源")


if __name__ == "__main__":
    unittest.main()
