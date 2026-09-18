import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np

from src import (
    AnalysisContext,
    EmptyLiveSessionError,
    LiveFrameShapeError,
    LiveFrameTimestampError,
    LivePetBehaviorAnalyzer,
    LiveSessionClosedError,
)


def make_context() -> AnalysisContext:
    return AnalysisContext(
        analysis_id="ANL-LIVE-001",
        pet_id="PET-001",
        video_id="VID-LIVE-001",
        camera_id="CAM-001",
        species="DOG",
        recorded_at="2026-09-17T15:00:00+09:00",
    )


class LivePetBehaviorAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_analyzer = Mock()
        self.mock_analyzer.analyze.return_value = {
            "schema_version": "1.2",
            "analysis_id": "ANL-LIVE-001",
        }
        class FakeDetector:
            def __init__(self):
                self.count = 0
            def track(self, frame):
                self.count += 1
                return [{"center_x": 16.0 + self.count * 0.2, "center_y": 24.0,
                         "track_id": 1, "confidence": 0.99, "class_id": 16}]
        self.live = LivePetBehaviorAnalyzer(
            analyzer=self.mock_analyzer,
            temp_root=self.temp_dir.name,
            detector_factory=lambda species: FakeDetector(),
        )
        self.frame = np.full((48, 64, 3), 127, dtype=np.uint8)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_frames_are_buffered_then_existing_analyzer_is_called(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 0.0)
        session.push_frame(self.frame, 0.1)
        result = session.finish()

        self.assertEqual(result["schema_version"], "1.2")
        call = self.mock_analyzer.analyze.call_args.kwargs
        self.assertTrue(Path(call["video_path"]).name.endswith("_live.avi"))
        self.assertEqual(call["species"], "DOG")
        self.assertFalse(Path(call["video_path"]).exists())

    def test_timestamp_gap_is_preserved_as_missing_video_slots(self):
        captured_count = []

        def inspect_video(**kwargs):
            capture = cv2.VideoCapture(str(kwargs["video_path"]))
            captured_count.append(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
            capture.release()
            return {"schema_version": "1.2"}

        self.mock_analyzer.analyze.side_effect = inspect_video
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 0.0)
        session.push_frame(self.frame, 0.3)
        session.finish()
        self.assertEqual(captured_count, [4])

    def test_timestamps_must_be_strictly_increasing(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 1.0)
        with self.assertRaises(LiveFrameTimestampError):
            session.push_frame(self.frame, 1.0)
        session.abort()

    def test_pipeline_failure_still_removes_temporary_video(self):
        captured_path = []

        def fail_pipeline(**kwargs):
            captured_path.append(Path(kwargs["video_path"]))
            raise RuntimeError("pipeline failed")

        self.mock_analyzer.analyze.side_effect = fail_pipeline
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 0.0)
        with self.assertRaisesRegex(RuntimeError, "pipeline failed"):
            session.finish()
        self.assertEqual(len(captured_path), 1)
        self.assertFalse(captured_path[0].exists())

    def test_frame_shape_cannot_change(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 0.0)
        with self.assertRaises(LiveFrameShapeError):
            session.push_frame(np.zeros((24, 32, 3), dtype=np.uint8), 0.1)
        session.abort()

    def test_empty_session_fails_without_calling_pipeline(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        with self.assertRaises(EmptyLiveSessionError):
            session.finish()
        self.mock_analyzer.analyze.assert_not_called()

    def test_abort_is_idempotent_and_closes_session(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        session.push_frame(self.frame, 0.0)
        session.abort()
        session.abort()
        with self.assertRaises(LiveSessionClosedError):
            session.push_frame(self.frame, 0.1)

    def test_completed_intervals_are_available_before_finish(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        for index in range(61):
            session.push_frame(self.frame, index / 10)
        intervals = session.poll_intervals()
        self.assertEqual(len(intervals), 1)
        self.assertEqual(intervals[0]["start_sec"], 0.0)
        self.assertIn("normalized_moving_speed", intervals[0])
        self.assertEqual(session.poll_intervals(), [])
        session.abort()

    def test_multiple_intervals_are_generated_in_order(self):
        session = self.live.start_session(context=make_context(), expected_fps=10)
        for index in range(111):
            session.push_frame(self.frame, index / 10)
        self.assertEqual([item["start_sec"] for item in session.poll_intervals()], [0.0, 5.0])
        session.abort()

    def test_open_roi_is_not_mislabeled_video_end_before_finish(self):
        context = make_context()
        context = AnalysisContext(**{**context.__dict__, "roi_data": {
            "camera_id": "CAM-001", "roi_areas": [{"roi_id": "ROI-1", "roi_name": "BED",
            "roi_type": "RECTANGLE", "x": 0.0, "y": 0.0, "width": 0.6, "height": 1.0}]}})
        session = self.live.start_session(context=context, expected_fps=10)
        for index in range(61): session.push_frame(self.frame, index / 10)
        roi = session.poll_intervals()[0]["space_analysis"]
        self.assertEqual(roi["roi_results"][0]["visit_events"], [])
        session.abort()


if __name__ == "__main__":
    unittest.main()
