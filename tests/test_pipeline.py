import json
import os
import pathlib
import unittest
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from src.extractor import extract_driver_profile
from src.ranker import load_loads, rank_loads


class TestDispatcherPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.here = pathlib.Path(__file__).parent.parent
        cls.workbook_path = cls.here / "data" / "Good_fit_test_clean.xlsx"
        cls.output_dir = cls.here / "output"

    def test_a_workbook_exists(self):
        """Verify the test workbook exists."""
        self.assertTrue(self.workbook_path.exists(), f"Workbook not found at {self.workbook_path}")

    def test_b_extractor(self):
        """Test driver profile extraction from Excel sheet using Groq API."""
        if not os.environ.get("GROQ_API_KEY"):
            self.skipTest("GROQ_API_KEY not set in environment; skipping API test")

        profile = extract_driver_profile(str(self.workbook_path))
        
        # Verify structure
        self.assertIsInstance(profile, dict)
        required_keys = {
            "current_location", "current_lat", "current_lon",
            "home_base", "home_lat", "home_lon",
            "min_rate_per_mile", "equipment_types", "weight_capacity_lb"
        }
        self.assertTrue(required_keys.issubset(profile.keys()), f"Missing keys: {required_keys - profile.keys()}")
        
        # Verify types
        self.assertIsInstance(profile["current_location"], str)
        self.assertIsInstance(profile["current_lat"], float)
        self.assertIsInstance(profile["current_lon"], float)
        self.assertIsInstance(profile["home_base"], str)
        self.assertIsInstance(profile["home_lat"], float)
        self.assertIsInstance(profile["home_lon"], float)
        self.assertIsInstance(profile["min_rate_per_mile"], (int, float))
        self.assertIsInstance(profile["equipment_types"], list)
        self.assertIsInstance(profile["weight_capacity_lb"], int)

        # Store profile for downstream test
        self.__class__.profile = profile

    def test_c_ranker(self):
        """Test load ranker and filtering logic."""
        # Use extracted profile if available, otherwise fallback to expected profile
        profile = getattr(self.__class__, "profile", {
            "current_location": "Dallas, TX",
            "current_lat": 32.7767,
            "current_lon": -96.7970,
            "home_base": "San Antonio, TX",
            "home_lat": 29.4241,
            "home_lon": -98.4936,
            "min_rate_per_mile": 2.0,
            "equipment_types": ["Hotshot", "Gooseneck"],
            "weight_capacity_lb": 44000,
        })
        
        loads_df = load_loads(str(self.workbook_path))
        self.assertFalse(loads_df.empty)

        ranking = rank_loads(loads_df, profile)
        self.assertIn("top3", ranking)
        self.assertIn("rejected", ranking)
        self.assertIn("all_eligible", ranking)

        # Verify Top 3 constraints
        self.assertLessEqual(len(ranking["top3"]), 3)
        for load in ranking["top3"]:
            self.assertIn("load_id", load)
            self.assertIn("effective_rate_per_mile", load)
            self.assertGreaterEqual(load["effective_rate_per_mile"], profile["min_rate_per_mile"])
            self.assertLessEqual(load["weight_lb"], profile["weight_capacity_lb"])
            self.assertIn(load["trailer"].lower(), [e.lower() for e in profile["equipment_types"]])

        # Verify that incomplete rows like L06 and L07 are skipped
        rejected_ids = [r["load_id"] for r in ranking["rejected"]]
        self.assertIn("L06", rejected_ids, "L06 should be skipped (missing price)")
        self.assertIn("L07", rejected_ids, "L07 should be skipped (missing destination coordinates)")


if __name__ == "__main__":
    unittest.main()
