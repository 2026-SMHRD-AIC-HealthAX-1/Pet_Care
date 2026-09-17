import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from roi_models import parse_roi_request  # noqa: E402
from roi_space_analyzer import (  # noqa: E402
    RoiAnalysisSettings,
    analyze_roi_usage,
)


def roi_request(multiple=False):
    areas = [
        {
            "roi_id": "ROI-001",
            "roi_name": "WATER_BOWL",
            "roi_type": "RECTANGLE",
            "x": 0.2,
            "y": 0.2,
            "width": 0.4,
            "height": 0.4,
        }
    ]
    if multiple:
        areas.append(
            {
                "roi_id": "ROI-002",
                "roi_name": "BED",
                "roi_type": "RECTANGLE",
                "x": 0.7,
                "y": 0.7,
                "width": 0.2,
                "height": 0.2,
            }
        )
    return parse_roi_request({"camera_id": "CAM-001", "roi_areas": areas})


def row(time_sec, x, y, status="detected", source_detected=True):
    return {
        "frame": int(time_sec * 10) + 1,
        "time_sec": time_sec,
        "center_x": x,
        "center_y": y,
        "source_detected": source_detected,
        "status": status,
    }


class RoiSpaceAnalyzerTest(unittest.TestCase):
    def test_none_request_returns_none(self):
        self.assertIsNone(analyze_roi_usage([], None, 100, 100))

    def test_inside_outside_and_boundary_are_inclusive(self):
        roi = roi_request().roi_areas[0]
        self.assertTrue(roi.contains(0.2, 0.2))
        self.assertTrue(roi.contains(0.6, 0.6))
        self.assertFalse(roi.contains(0.19, 0.2))

    def test_approach_count_and_timestamp_based_stay(self):
        result = analyze_roi_usage(
            [
                row(0.0, 10, 10),
                row(1.0, 30, 30),
                row(2.25, 35, 35),
                row(3.0, 10, 10),
                row(4.5, 40, 40),
                row(6.0, 45, 45),
            ],
            roi_request(),
            100,
            100,
        )
        roi = result["roi_results"][0]
        self.assertEqual(2, roi["approach_count"])
        self.assertEqual([1.0, 4.5], roi["approach_times_sec"])
        self.assertEqual(1.0, roi["first_approach_time_sec"])
        self.assertAlmostEqual(2.75, roi["stay_time_sec"])
        self.assertEqual(
            [
                {
                    "event_index": 1,
                    "entry_time_sec": 1.0,
                    "exit_time_sec": 3.0,
                    "stay_time_sec": 1.25,
                    "end_reason": "EXIT",
                },
                {
                    "event_index": 2,
                    "entry_time_sec": 4.5,
                    "exit_time_sec": None,
                    "stay_time_sec": 1.5,
                    "end_reason": "VIDEO_END",
                },
            ],
            roi["visit_events"],
        )

    def test_interpolated_position_is_valid(self):
        result = analyze_roi_usage(
            [
                row(0.0, 30, 30),
                row(1.0, 35, 35, "interpolated", False),
            ],
            roi_request(),
            100,
            100,
        )
        roi = result["roi_results"][0]
        self.assertEqual(1, roi["approach_count"])
        self.assertEqual(1.0, roi["stay_time_sec"])

    def test_missing_pauses_stay_and_does_not_create_reentry(self):
        result = analyze_roi_usage(
            [
                row(0.0, 30, 30),
                row(1.0, 35, 35),
                row(2.0, "", "", "missing", False),
                row(3.0, 40, 40),
                row(4.0, 45, 45),
            ],
            roi_request(),
            100,
            100,
        )
        roi = result["roi_results"][0]
        self.assertEqual(1, roi["approach_count"])
        self.assertEqual(2.0, roi["stay_time_sec"])
        self.assertEqual(1, len(roi["visit_events"]))
        self.assertEqual("VIDEO_END", roi["visit_events"][0]["end_reason"])

    def test_multiple_rois_are_independent(self):
        result = analyze_roi_usage(
            [row(0.0, 30, 30), row(1.0, 80, 80)],
            roi_request(multiple=True),
            100,
            100,
        )
        self.assertEqual(
            [1, 1],
            [item["approach_count"] for item in result["roi_results"]],
        )

    def test_minimum_stay_filters_short_event(self):
        result = analyze_roi_usage(
            [row(0.0, 30, 30), row(0.25, 35, 35), row(0.5, 10, 10)],
            roi_request(),
            100,
            100,
            RoiAnalysisSettings(minimum_stay_sec=0.5),
        )
        roi = result["roi_results"][0]
        self.assertEqual(0, roi["approach_count"])
        self.assertEqual([], roi["visit_events"])

    def test_confirmation_settings_are_separate_and_default_to_zero(self):
        defaults = RoiAnalysisSettings()
        self.assertEqual(0.0, defaults.entry_confirmation_sec)
        self.assertEqual(0.0, defaults.exit_confirmation_sec)
        self.assertEqual(0.0, defaults.minimum_stay_sec)

        result = analyze_roi_usage(
            [
                row(0.0, 10, 10),
                row(0.1, 30, 30),
                row(0.4, 30, 30),
                row(0.6, 30, 30),
            ],
            roi_request(),
            100,
            100,
            RoiAnalysisSettings(entry_confirmation_sec=0.5),
        )
        self.assertEqual(1, result["roi_results"][0]["approach_count"])
        self.assertEqual(0.1, result["roi_results"][0]["first_approach_time_sec"])

    def test_decreasing_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_roi_usage(
                [row(2.0, 30, 30), row(1.0, 30, 30)],
                roi_request(),
                100,
                100,
            )


if __name__ == "__main__":
    unittest.main()
