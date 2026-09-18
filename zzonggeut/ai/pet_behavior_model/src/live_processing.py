"""Shared-policy helpers for incremental LIVE tracking and feature windows."""

from __future__ import annotations

import bisect
import math
from collections import Counter
from typing import Any, Iterable


PET_CLASS_IDS = {"cat": 15, "dog": 16}
PET_CLASS_NAMES = {15: "cat", 16: "dog"}
YOLO_IMAGE_SIZE = 960
YOLO_CONFIDENCE = 0.15
YOLO_IOU = 0.50
MAX_GAP_SECONDS = 1.0
MAX_JUMP_RATIO = 0.12
SMOOTHING_ALPHA = 0.35
MOVEMENT_WINDOW_SECONDS = 1.0
WINDOW_TOLERANCE_SECONDS = 0.15
MOVING_SPEED_THRESHOLD = 0.04
AGGREGATION_SECONDS = 5.0
MAX_INTEGRATION_GAP_SECONDS = 0.25


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def postprocess_tracking(
    source_records: Iterable[dict[str, Any]], expected_fps: float, frame_diagonal: float
) -> list[dict[str, Any]]:
    """Apply the same gap, jump and EMA policies used by ``track_pet.py``."""
    records = [dict(record) for record in source_records]
    max_gap_frames = max(1, int(round(expected_fps * MAX_GAP_SECONDS)))
    index = 0
    while index < len(records):
        if records[index]["raw_x"] is not None:
            index += 1
            continue
        gap_start = index
        while index < len(records) and records[index]["raw_x"] is None:
            index += 1
        gap_end = index - 1
        previous_index = gap_start - 1
        next_index = index
        gap_length = gap_end - gap_start + 1
        if not (
            gap_length <= max_gap_frames
            and previous_index >= 0
            and next_index < len(records)
            and records[previous_index]["raw_x"] is not None
            and records[next_index]["raw_x"] is not None
        ):
            continue
        start_x, start_y = records[previous_index]["raw_x"], records[previous_index]["raw_y"]
        end_x, end_y = records[next_index]["raw_x"], records[next_index]["raw_y"]
        for step in range(1, gap_length + 1):
            ratio = step / (gap_length + 1)
            target = records[previous_index + step]
            target["raw_x"] = start_x + (end_x - start_x) * ratio
            target["raw_y"] = start_y + (end_y - start_y) * ratio
            target["status"] = "interpolated"

    previous_x = previous_y = None
    max_jump = frame_diagonal * MAX_JUMP_RATIO
    for record in records:
        current_x, current_y = record["raw_x"], record["raw_y"]
        if current_x is None or current_y is None:
            continue
        if previous_x is None:
            previous_x, previous_y = current_x, current_y
        elif distance(previous_x, previous_y, current_x, current_y) > max_jump:
            record["raw_x"], record["raw_y"] = previous_x, previous_y
            record["status"] = (
                "jump_filtered" if record["status"] == "detected"
                else record["status"] + "+jump_filtered"
            )
        else:
            previous_x, previous_y = current_x, current_y

    smooth_x = smooth_y = None
    for record in records:
        current_x, current_y = record["raw_x"], record["raw_y"]
        if current_x is None or current_y is None:
            record["center_x"] = record["center_y"] = None
        elif smooth_x is None:
            smooth_x, smooth_y = current_x, current_y
            record["center_x"], record["center_y"] = smooth_x, smooth_y
        else:
            smooth_x = SMOOTHING_ALPHA * current_x + (1 - SMOOTHING_ALPHA) * smooth_x
            smooth_y = SMOOTHING_ALPHA * current_y + (1 - SMOOTHING_ALPHA) * smooth_y
            record["center_x"], record["center_y"] = smooth_x, smooth_y
    return records


def calculate_movements(rows: list[dict[str, Any]], frame_diagonal: float) -> list[dict[str, Any]]:
    times = [row["time_sec"] for row in rows]
    movements: list[dict[str, Any]] = []
    for current_index, current in enumerate(rows):
        if current["center_x"] is None or current["center_y"] is None:
            continue
        target_time = current["time_sec"] - MOVEMENT_WINDOW_SECONDS
        if not times or target_time < times[0]:
            continue
        insertion = bisect.bisect_left(times, target_time, 0, current_index)
        candidates = []
        for index in range(max(0, insertion - 4), min(current_index, insertion + 4)):
            row = rows[index]
            if row["center_x"] is None or row["center_y"] is None:
                continue
            difference = abs(row["time_sec"] - target_time)
            if difference <= WINDOW_TOLERANCE_SECONDS:
                candidates.append((difference, row))
        if not candidates:
            continue
        previous = min(candidates, key=lambda item: item[0])[1]
        delta_time = current["time_sec"] - previous["time_sec"]
        if not (0.85 <= delta_time <= 1.15):
            continue
        normalized_distance = distance(
            previous["center_x"], previous["center_y"], current["center_x"], current["center_y"]
        ) / frame_diagonal
        speed = normalized_distance / delta_time
        is_moving = speed >= MOVING_SPEED_THRESHOLD
        movements.append({
            "frame": current["frame"], "time_sec": current["time_sec"],
            "window_start_sec": previous["time_sec"], "window_duration_sec": delta_time,
            "distance_normalized": normalized_distance, "speed_normalized": speed,
            "effective_speed": speed if is_moving else 0.0, "is_moving": is_moving,
        })
    return movements


def calculate_features(movements: list[dict[str, Any]]) -> dict[str, Any]:
    if not movements:
        return {"activity_level": 0.0, "stationary_ratio": 0.0, "travel_distance": 0.0,
                "moving_speed": 0.0, "moving_count": 0, "stationary_count": 0,
                "measurement_count": 0, "analyzed_duration": 0.0}
    moving = [item for item in movements if item["is_moving"]]
    travel_distance = 0.0
    for previous, current in zip(movements, movements[1:]):
        integration_time = current["time_sec"] - previous["time_sec"]
        if 0 < integration_time <= MAX_INTEGRATION_GAP_SECONDS:
            travel_distance += (
                (previous["effective_speed"] + current["effective_speed"]) / 2 * integration_time
            )
    return {
        "activity_level": sum(item["effective_speed"] for item in movements) / len(movements),
        "stationary_ratio": (len(movements) - len(moving)) / len(movements),
        "travel_distance": travel_distance,
        "moving_speed": sum(item["speed_normalized"] for item in moving) / len(moving) if moving else 0.0,
        "moving_count": len(moving), "stationary_count": len(movements) - len(moving),
        "measurement_count": len(movements),
        "analyzed_duration": movements[-1]["time_sec"] - movements[0]["time_sec"] if len(movements) >= 2 else 0.0,
    }


def interval_features(rows: list[dict[str, Any]], frame_diagonal: float, complete_only: bool,
                      end_time: float | None = None) -> list[dict[str, Any]]:
    movements = calculate_movements(rows, frame_diagonal)
    groups: dict[int, list[dict[str, Any]]] = {}
    for movement in movements:
        groups.setdefault(int(movement["time_sec"] // AGGREGATION_SECONDS), []).append(movement)
    actual_end = end_time if end_time is not None else (rows[-1]["time_sec"] if rows else 0.0)
    results = []
    for index in sorted(groups):
        start = index * AGGREGATION_SECONDS
        full_end = start + AGGREGATION_SECONDS
        if complete_only and actual_end < full_end:
            continue
        features = calculate_features(groups[index])
        results.append({"interval_start_sec": start, "interval_end_sec": min(full_end, actual_end), **features})
    return results


def tracking_quality(records: list[dict[str, Any]], species: str) -> dict[str, Any]:
    total = len(records)
    detected = sum(bool(row["source_detected"]) for row in records)
    interpolated = sum("interpolated" in row["status"] for row in records)
    missing = sum(row["center_x"] is None for row in records)
    jumped = sum("jump_filtered" in row["status"] for row in records)
    detection_rate = detected / total if total else 0.0
    interpolation_ratio = interpolated / total if total else 0.0
    missing_ratio = missing / total if total else 1.0
    if detection_rate >= .85 and missing_ratio <= .05 and interpolation_ratio <= .15:
        quality = "GOOD"
    elif detection_rate >= .65 and missing_ratio <= .15 and interpolation_ratio <= .30:
        quality = "WARNING"
    else:
        quality = "LOW_QUALITY"
    predicted = [row["predicted_type"] for row in records if row.get("predicted_type")]
    return {"registered_pet_type": species.lower(), "detected_pet_type": species.lower(),
            "most_predicted_type": Counter(predicted).most_common(1)[0][0] if predicted else "unknown",
            "total_frames": total, "raw_detected_frames": detected, "interpolated_frames": interpolated,
            "missing_frames": missing, "jump_filtered_frames": jumped,
            "detection_rate": detection_rate, "interpolation_ratio": interpolation_ratio,
            "missing_ratio": missing_ratio,
            "raw_track_id_count": len({row["raw_track_id"] for row in records if row.get("raw_track_id") is not None}),
            "tracking_quality": quality, "analysis_allowed": quality != "LOW_QUALITY"}
