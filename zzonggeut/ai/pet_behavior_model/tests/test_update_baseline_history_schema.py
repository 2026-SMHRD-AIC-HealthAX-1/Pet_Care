import unittest

from src.update_baseline_history import validate_analysis_result


def make_result(schema_version):
    return {
        "schema_version": schema_version,
        "analysis_id": "ANL-001",
        "pet_id": "PET-001",
        "video_id": "VID-001",
        "camera_id": "CAM-001",
        "analysis_status": "COMPLETED",
        "recorded_at": "2026-09-17T10:00:00+09:00",
        "aggregation_sec": 5.0,
        "time_slot": "10:00-11:00",
        "tracking_quality": {"quality_status": "GOOD"},
        "change_detection": {"change_status": "NOT_EVALUATED"},
        "model_info": {"feature_version": "pet-features-v2.0"},
        "video_info": {"file_name": "sample.mp4"},
    }


class AnalysisResultSchemaCompatibilityTest(unittest.TestCase):
    def test_schema_11_is_accepted(self):
        metadata = validate_analysis_result(make_result("1.1"))
        self.assertEqual(metadata["analysis_id"], "ANL-001")

    def test_schema_12_is_accepted(self):
        metadata = validate_analysis_result(make_result("1.2"))
        self.assertEqual(metadata["analysis_id"], "ANL-001")

    def test_unknown_schema_is_rejected(self):
        with self.assertRaisesRegex(Exception, "1.1 또는 1.2"):
            validate_analysis_result(make_result("2.0"))


if __name__ == "__main__":
    unittest.main()
