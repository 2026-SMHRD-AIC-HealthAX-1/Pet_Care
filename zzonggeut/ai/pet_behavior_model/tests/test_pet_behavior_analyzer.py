import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pet_behavior_analyzer import (
    AnalysisConflictError,
    AnalyzerInputError,
    PetBehaviorAnalyzer,
    PipelineExecutionError,
)


PROJECT_DIR = Path(__file__).resolve().parent.parent


def make_result(**overrides):
    result = {
        "schema_version": "1.2",
        "analysis_id": "ANL-001",
        "pet_id": "PET-001",
        "video_id": "VID-001",
        "camera_id": "CAM-001",
        "species": "DOG",
        "analysis_status": "COMPLETED",
        "recorded_at": "2026-09-16T10:00:00+09:00",
        "recorded_at_source": "REQUEST_TIME",
        "aggregation_sec": 5.0,
        "time_slot": "10:00-11:00",
        "started_at": "2026-09-16T10:00:01+09:00",
        "completed_at": "2026-09-16T10:00:02+09:00",
        "video_info": {
            "file_name": "video.mp4", "duration_sec": 10.0, "fps": 30.0,
            "width": 1920, "height": 1080, "total_frames": 300,
        },
        "tracking_quality": {
            "raw_detected_frames": 300, "interpolated_frames": 0,
            "jump_filtered_frames": 0, "valid_tracking_frames": 300,
            "missing_frames": 0, "tracking_success_rate": 1.0,
            "quality_status": "GOOD",
        },
        "features_overall": {
            "activity_level": 0.1, "stationary_ratio": 0.5,
            "normalized_travel_distance": 0.2, "normalized_moving_speed": 0.1,
        },
        "features_by_interval": [{
            "start_sec": 0.0, "end_sec": 5.0, "valid_tracking_frames": 150,
            "activity_level": 0.1, "stationary_ratio": 0.5,
            "normalized_travel_distance": 0.1, "normalized_moving_speed": 0.1,
        }],
        "baseline_comparison": [],
        "change_detection": {
            "baseline_status": "NOT_READY", "change_score": None,
            "change_status": "NOT_EVALUATED", "evaluated_feature_count": 0,
            "threshold_exceeded_count": 0, "contributing_factors": [],
        },
        "space_analysis": None,
        "model_info": {
            "pipeline_version": "pet-behavior-v1.2",
            "feature_version": "pet-features-v2.0", "detector": "YOLO11s",
            "movement_window_sec": 1.0, "movement_threshold": 0.04,
            "aggregation_sec": 5.0, "std_zero_policy": "EXCLUDE_FEATURE",
        },
        "warnings": [],
        "error": None,
    }
    result.update(overrides)
    return result


class PetBehaviorAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        (self.base_dir / "src").mkdir()
        (self.base_dir / "src" / "run_pipeline.py").write_text("# test\n", encoding="utf-8")
        (self.base_dir / "schemas").mkdir()
        shutil.copy2(
            PROJECT_DIR / "schemas" / "analysis_result_v1.2.schema.json",
            self.base_dir / "schemas" / "analysis_result_v1.2.schema.json",
        )
        self.analyzer = PetBehaviorAnalyzer(base_dir=self.base_dir)
        self.kwargs = {
            "video_path": self.base_dir / "video.mp4",
            "analysis_id": "ANL-001",
            "pet_id": "PET-001",
            "video_id": "VID-001",
            "camera_id": "CAM-001",
            "species": "DOG",
            "recorded_at": "2026-09-16T10:00:00+09:00",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def result_path(self):
        return self.base_dir / "data" / "outputs" / "analysis_results" / "ANL-001_result.json"

    def write_result(self, result):
        self.result_path().parent.mkdir(parents=True, exist_ok=True)
        self.result_path().write_text(json.dumps(result), encoding="utf-8")

    def fake_run(self, result, captured=None):
        def run(command, **kwargs):
            if captured is not None:
                captured.extend(command)
            self.write_result(result)
            return subprocess.CompletedProcess(command, 0, "ok")
        return run

    def test_success_returns_schema_12_dict(self):
        with patch("src.pet_behavior_analyzer.subprocess.run", self.fake_run(make_result())):
            result = self.analyzer.analyze(**self.kwargs)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["analysis_status"], "COMPLETED")

    def test_failed_schema_result_is_returned(self):
        failed = make_result(
            analysis_status="FAILED", video_info=None, tracking_quality=None,
            features_overall=None, error={"code": "PET_NOT_DETECTED", "message": "none"},
        )
        with patch("src.pet_behavior_analyzer.subprocess.run", self.fake_run(failed)):
            result = self.analyzer.analyze(**self.kwargs)
        self.assertEqual(result["analysis_status"], "FAILED")

    def test_none_and_empty_roi_omit_cli_option(self):
        for roi_data in (None, {"camera_id": "CAM-001", "roi_areas": []}):
            self.result_path().unlink(missing_ok=True)
            captured = []
            with patch("src.pet_behavior_analyzer.subprocess.run", self.fake_run(make_result(), captured)):
                result = self.analyzer.analyze(**self.kwargs, roi_data=roi_data)
            self.assertNotIn("--roi-request-json", captured)
            self.assertIsNone(result["space_analysis"])

    def test_valid_roi_uses_cli_file_and_returns_space_analysis(self):
        roi = {
            "camera_id": "CAM-001",
            "roi_areas": [{
                "roi_id": "BED-1", "roi_name": "BED", "roi_type": "RECTANGLE",
                "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4,
            }],
        }
        space = {
            "calculation_version": "roi-space-v2", "point_policy": "BBOX_CENTER",
            "settings": {"entry_confirmation_sec": 0, "exit_confirmation_sec": 0, "minimum_stay_sec": 0},
            "roi_results": [{**roi["roi_areas"][0], "approach_count": 1, "stay_time_sec": 2.0,
                             "first_approach_time_sec": 1.0, "approach_times_sec": [1.0],
                             "visit_events": [{"event_index": 1, "entry_time_sec": 1.0,
                                                "exit_time_sec": 3.0, "stay_time_sec": 2.0,
                                                "end_reason": "EXIT"}]}],
        }
        captured = []
        with patch("src.pet_behavior_analyzer.subprocess.run", self.fake_run(make_result(space_analysis=space), captured)):
            result = self.analyzer.analyze(**self.kwargs, roi_data=roi)
        self.assertIn("--roi-request-json", captured)
        self.assertEqual(result["space_analysis"]["roi_results"][0]["roi_id"], "BED-1")

    def test_invalid_roi_and_camera_mismatch_are_rejected(self):
        invalid = {"camera_id": "CAM-001", "roi_areas": [{"roi_id": "X"}]}
        mismatch = {"camera_id": "OTHER", "roi_areas": []}
        with self.assertRaises(AnalyzerInputError):
            self.analyzer.analyze(**self.kwargs, roi_data=invalid)
        with self.assertRaises(AnalyzerInputError):
            self.analyzer.analyze(**self.kwargs, roi_data=mismatch)

    def test_identical_request_reuses_result_without_pipeline(self):
        self.write_result(make_result())
        with patch("src.pet_behavior_analyzer.subprocess.run") as run:
            result = self.analyzer.analyze(**self.kwargs)
        run.assert_not_called()
        self.assertEqual(result["analysis_id"], "ANL-001")

    def test_identical_roi_request_reuses_result_without_pipeline(self):
        roi = {
            "camera_id": "CAM-001",
            "roi_areas": [{
                "roi_id": "BED-1", "roi_name": "BED", "roi_type": "RECTANGLE",
                "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4,
            }],
        }
        space = {
            "calculation_version": "roi-space-v2", "point_policy": "BBOX_CENTER",
            "settings": {"entry_confirmation_sec": 0, "exit_confirmation_sec": 0, "minimum_stay_sec": 0},
            "roi_results": [{**roi["roi_areas"][0], "approach_count": 0, "stay_time_sec": 0,
                             "first_approach_time_sec": None, "approach_times_sec": [],
                             "visit_events": []}],
        }
        self.write_result(make_result(space_analysis=space))
        with patch("src.pet_behavior_analyzer.subprocess.run") as run:
            result = self.analyzer.analyze(**self.kwargs, roi_data=roi)
        run.assert_not_called()
        self.assertEqual("BED-1", result["space_analysis"]["roi_results"][0]["roi_id"])

    def test_same_analysis_id_with_different_roi_is_rejected(self):
        existing_roi = {
            "roi_id": "BED-1", "roi_name": "BED", "roi_type": "RECTANGLE",
            "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4,
        }
        self.write_result(make_result(space_analysis={
            "calculation_version": "roi-space-v2", "point_policy": "BBOX_CENTER",
            "settings": {"entry_confirmation_sec": 0, "exit_confirmation_sec": 0, "minimum_stay_sec": 0},
            "roi_results": [{**existing_roi, "approach_count": 0, "stay_time_sec": 0,
                             "first_approach_time_sec": None, "approach_times_sec": [],
                             "visit_events": []}],
        }))
        different_roi = {
            "camera_id": "CAM-001",
            "roi_areas": [{**existing_roi, "x": 0.2}],
        }
        with self.assertRaises(AnalysisConflictError):
            self.analyzer.analyze(**self.kwargs, roi_data=different_roi)

    def test_analysis_id_conflict_is_rejected(self):
        self.write_result(make_result(pet_id="PET-OTHER"))
        with self.assertRaises(AnalysisConflictError):
            self.analyzer.analyze(**self.kwargs)

    def test_missing_result_raises_pipeline_error(self):
        completed = subprocess.CompletedProcess([], 2, "failed")
        with patch("src.pet_behavior_analyzer.subprocess.run", return_value=completed):
            with self.assertRaises(PipelineExecutionError):
                self.analyzer.analyze(**self.kwargs)

    def test_process_start_failure_raises_pipeline_error(self):
        with patch("src.pet_behavior_analyzer.subprocess.run", side_effect=OSError("no python")):
            with self.assertRaises(PipelineExecutionError):
                self.analyzer.analyze(**self.kwargs)


if __name__ == "__main__":
    unittest.main()
