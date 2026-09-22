"""5 FPS LIVE + ROI regression using real YOLO/ByteTrack."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import cv2

from src import AnalysisContext, LivePetBehaviorAnalyzer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("species", choices=["DOG", "CAT"])
    parser.add_argument("--camera-id", default="CAM-LIVE-ROI")
    parser.add_argument("--target-fps", type=float, default=5.0)
    args = parser.parse_args()

    video_path = args.video.resolve()

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS)

    if source_fps <= 0:
        capture.release()
        raise SystemExit("Source FPS must be positive.")

    token = uuid.uuid4().hex[:10]

    roi_data = {
        "camera_id": args.camera_id,
        "roi_areas": [
            {
                "roi_id": "ROI-LIVE-TEST-001",
                "roi_name": "ETC",
                "roi_type": "RECTANGLE",
                "x": 0.0,
                "y": 0.0,
                "width": 1.0,
                "height": 1.0
            }
        ]
    }

    context = AnalysisContext(
        analysis_id=f"ANL-LIVE-ROI-{token}",
        pet_id=f"PET-{args.species}-ROI-{token}",
        video_id=f"VID-LIVE-ROI-{token}",
        camera_id=args.camera_id,
        species=args.species,
        recorded_at=time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        roi_data=roi_data,
    )

    session = LivePetBehaviorAnalyzer().start_session(
        context=context,
        expected_fps=args.target_fps,
    )

    started = time.perf_counter()

    source_frame_index = 0
    sampled_frame_count = 0
    next_sample_time = 0.0

    interval_results = []

    while True:
        ok, frame = capture.read()

        if not ok:
            break

        source_time = source_frame_index / source_fps

        if source_time + 1e-9 >= next_sample_time:
            live_timestamp = sampled_frame_count / args.target_fps

            emitted = session.push_frame(
                frame,
                live_timestamp,
            )

            sampled_frame_count += 1
            next_sample_time = sampled_frame_count / args.target_fps

            if emitted is not None:
                interval_results.append({
                    "start_sec": emitted.get("start_sec"),
                    "end_sec": emitted.get("end_sec"),
                    "activity_level": emitted.get("activity_level"),
                    "stationary_ratio": emitted.get("stationary_ratio"),
                    "space_analysis": emitted.get("space_analysis"),
                    "wall_sec": time.perf_counter() - started,
                })

        source_frame_index += 1

    capture.release()

    metrics = session.metrics()
    result = session.finish()

    processing_fps = metrics.get("processing_fps")

    payload = {
        "analysis_id": context.analysis_id,
        "live_status": result.get("analysis_status"),
        "live_schema": result.get("schema_version"),

        "source_fps": source_fps,
        "target_fps": args.target_fps,
        "source_frames_read": source_frame_index,
        "sampled_frames": sampled_frame_count,

        "processing_fps": processing_fps,
        "backlog_risk": (
            processing_fps is not None
            and processing_fps < args.target_fps
        ),

        "tracking_quality": result.get("tracking_quality"),
        "features_overall": result.get("features_overall"),

        "interval_count": len(interval_results),
        "interval_results": interval_results,

        "space_analysis": result.get("space_analysis"),
    }

    print(json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()


