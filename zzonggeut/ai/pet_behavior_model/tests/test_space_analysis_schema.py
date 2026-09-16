import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from roi_models import parse_roi_request  # noqa: E402
from roi_space_analyzer import analyze_roi_usage  # noqa: E402


class SpaceAnalysisSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "analysis_result.schema.json")
            .read_text(encoding="utf-8-sig")
        )
        cls.validator = Draft202012Validator(
            schema["properties"]["space_analysis"]
        )

    def test_null_space_analysis_is_valid(self):
        self.assertEqual([], list(self.validator.iter_errors(None)))

    def test_roi_object_is_valid(self):
        request = parse_roi_request(
            {
                "camera_id": "CAM-001",
                "roi_areas": [
                    {
                        "roi_id": "ROI-001",
                        "roi_name": "FOOD_BOWL",
                        "roi_type": "RECTANGLE",
                        "x": 0.1,
                        "y": 0.2,
                        "width": 0.3,
                        "height": 0.4,
                    }
                ],
            }
        )
        value = analyze_roi_usage([], request, 1920, 1080)
        self.assertEqual([], list(self.validator.iter_errors(value)))

    def test_invalid_roi_object_is_rejected(self):
        invalid = {
            "calculation_version": "roi-space-v1",
            "point_policy": "HEAD_POINT",
            "settings": {
                "entry_confirmation_sec": 0.0,
                "exit_confirmation_sec": 0.0,
                "minimum_stay_sec": 0.0,
            },
            "roi_results": [],
        }
        self.assertNotEqual([], list(self.validator.iter_errors(invalid)))


if __name__ == "__main__":
    unittest.main()
