import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from roi_models import RoiValidationError, parse_roi_request  # noqa: E402


def request_with(**area_overrides):
    area = {
        "roi_id": "ROI-001",
        "roi_name": "WATER_BOWL",
        "roi_type": "RECTANGLE",
        "x": 0.1,
        "y": 0.2,
        "width": 0.3,
        "height": 0.4,
    }
    area.update(area_overrides)
    return {"camera_id": "CAM-001", "roi_areas": [area]}


class RoiModelsTest(unittest.TestCase):
    def test_missing_and_empty_roi_are_none(self):
        self.assertIsNone(parse_roi_request(None))
        self.assertIsNone(
            parse_roi_request({"camera_id": "CAM-001", "roi_areas": []})
        )

    def test_valid_rectangle_and_camera_match(self):
        parsed = parse_roi_request(
            request_with(),
            expected_camera_id="CAM-001",
        )
        self.assertEqual("ROI-001", parsed.roi_areas[0].roi_id)

    def test_multiple_rois(self):
        request = request_with()
        second = dict(request["roi_areas"][0])
        second.update({"roi_id": "ROI-002", "roi_name": "BED"})
        request["roi_areas"].append(second)
        self.assertEqual(2, len(parse_roi_request(request).roi_areas))

    def test_negative_and_out_of_range_coordinates(self):
        for field, value in (("x", -0.1), ("y", 1.1)):
            with self.subTest(field=field):
                with self.assertRaises(RoiValidationError):
                    parse_roi_request(request_with(**{field: value}))

    def test_rectangle_must_fit_in_normalized_frame(self):
        for overrides in (
            {"x": 0.8, "width": 0.3},
            {"y": 0.9, "height": 0.2},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(RoiValidationError):
                    parse_roi_request(request_with(**overrides))

    def test_dimensions_must_be_positive(self):
        with self.assertRaises(RoiValidationError):
            parse_roi_request(request_with(width=0.0))

    def test_wrong_type_and_name_are_rejected(self):
        with self.assertRaises(RoiValidationError):
            parse_roi_request(request_with(roi_type="POLYGON"))
        with self.assertRaises(RoiValidationError):
            parse_roi_request(request_with(roi_name="SOFA"))

    def test_duplicate_roi_id_is_rejected(self):
        request = request_with()
        request["roi_areas"].append(dict(request["roi_areas"][0]))
        with self.assertRaises(RoiValidationError):
            parse_roi_request(request)

    def test_camera_mismatch_is_rejected(self):
        with self.assertRaises(RoiValidationError):
            parse_roi_request(request_with(), expected_camera_id="CAM-002")


if __name__ == "__main__":
    unittest.main()
