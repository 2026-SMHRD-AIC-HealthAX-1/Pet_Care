import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

try:
    from .roi_models import RoiRequest
except ImportError:
    from roi_models import RoiRequest


@dataclass(frozen=True)
class RoiAnalysisSettings:
    entry_confirmation_sec: float = 0.0
    exit_confirmation_sec: float = 0.0
    minimum_stay_sec: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in (
            ("entry_confirmation_sec", self.entry_confirmation_sec),
            ("exit_confirmation_sec", self.exit_confirmation_sec),
            ("minimum_stay_sec", self.minimum_stay_sec),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
            ):
                raise ValueError(f"{field_name} must be a finite non-negative number.")


def load_tracking_csv(path: Path | str) -> list[dict[str, Any]]:
    """Load only the existing tracking fields needed by ROI analysis."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {
            "frame",
            "time_sec",
            "center_x",
            "center_y",
            "source_detected",
            "status",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Tracking CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )
        return list(reader)


def _optional_float(value: Any, field_name: str) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric.") from error
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _normalize_tracking_rows(
    rows: Iterable[Mapping[str, Any]],
    frame_width: int,
    frame_height: int,
) -> list[dict[str, Any]]:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame_width and frame_height must be greater than 0.")

    normalized_rows = []
    previous_time: Optional[float] = None
    for row_index, row in enumerate(rows):
        time_sec = _optional_float(row.get("time_sec"), "time_sec")
        if time_sec is None or time_sec < 0.0:
            raise ValueError(f"Tracking row {row_index} has an invalid time_sec.")
        if previous_time is not None and time_sec < previous_time:
            raise ValueError("Tracking timestamps must be non-decreasing.")
        previous_time = time_sec

        center_x = _optional_float(row.get("center_x"), "center_x")
        center_y = _optional_float(row.get("center_y"), "center_y")
        status = str(row.get("status", "")).strip().lower()
        has_position = center_x is not None and center_y is not None

        # Interpolated positions are valid post-processed tracking points.
        # A row without both coordinates is UNKNOWN regardless of status.
        normalized_rows.append(
            {
                "time_sec": time_sec,
                "status": status,
                "has_position": has_position,
                "x": center_x / frame_width if has_position else None,
                "y": center_y / frame_height if has_position else None,
            }
        )

    return normalized_rows


def _round_seconds(value: float) -> float:
    return round(max(value, 0.0), 6)


def analyze_roi_usage(
    tracking_rows: Iterable[Mapping[str, Any]],
    roi_request: Optional[RoiRequest],
    frame_width: int,
    frame_height: int,
    settings: RoiAnalysisSettings = RoiAnalysisSettings(),
) -> Optional[dict[str, Any]]:
    """Calculate ROI visits from existing tracking rows without rerunning YOLO."""
    if roi_request is None or not roi_request.roi_areas:
        return None

    rows = _normalize_tracking_rows(
        tracking_rows,
        frame_width,
        frame_height,
    )
    states = {
        roi.roi_id: {
            "confirmed_inside": False,
            "candidate_inside": None,
            "candidate_since": None,
            "previous_row_valid": False,
            "previous_time": None,
            "current_approach_time": None,
            "current_stay_time": 0.0,
            "visits": [],
        }
        for roi in roi_request.roi_areas
    }

    for row in rows:
        for roi in roi_request.roi_areas:
            state = states[roi.roi_id]
            if not row["has_position"]:
                # UNKNOWN pauses duration accumulation but intentionally keeps
                # the last known inside/outside state to prevent false re-entry.
                state["previous_row_valid"] = False
                state["previous_time"] = row["time_sec"]
                state["candidate_inside"] = None
                state["candidate_since"] = None
                continue

            inside = roi.contains(row["x"], row["y"])
            previous_time = state["previous_time"]
            if (
                inside
                and state["confirmed_inside"]
                and state["previous_row_valid"]
                and previous_time is not None
            ):
                state["current_stay_time"] += max(
                    row["time_sec"] - previous_time,
                    0.0,
                )

            if inside == state["confirmed_inside"]:
                state["candidate_inside"] = None
                state["candidate_since"] = None
            else:
                if state["candidate_inside"] != inside:
                    state["candidate_inside"] = inside
                    state["candidate_since"] = row["time_sec"]

                confirmation_sec = (
                    settings.entry_confirmation_sec
                    if inside
                    else settings.exit_confirmation_sec
                )
                candidate_elapsed = (
                    row["time_sec"] - state["candidate_since"]
                )
                if candidate_elapsed >= confirmation_sec:
                    if inside:
                        state["confirmed_inside"] = True
                        state["current_approach_time"] = state[
                            "candidate_since"
                        ]
                        state["current_stay_time"] = 0.0
                    else:
                        if (
                            state["current_approach_time"] is not None
                            and state["current_stay_time"]
                            >= settings.minimum_stay_sec
                        ):
                            state["visits"].append(
                                {
                                    "entry_time_sec": state["current_approach_time"],
                                    "exit_time_sec": state["candidate_since"],
                                    "stay_time_sec": state["current_stay_time"],
                                    "end_reason": "EXIT",
                                }
                            )
                        state["confirmed_inside"] = False
                        state["current_approach_time"] = None
                        state["current_stay_time"] = 0.0

                    state["candidate_inside"] = None
                    state["candidate_since"] = None

            state["previous_row_valid"] = True
            state["previous_time"] = row["time_sec"]

    roi_results = []
    for roi in roi_request.roi_areas:
        state = states[roi.roi_id]
        if (
            state["confirmed_inside"]
            and state["current_approach_time"] is not None
            and state["current_stay_time"] >= settings.minimum_stay_sec
        ):
            state["visits"].append(
                {
                    "entry_time_sec": state["current_approach_time"],
                    "exit_time_sec": None,
                    "stay_time_sec": state["current_stay_time"],
                    "end_reason": "VIDEO_END",
                }
            )

        approach_times = [
            _round_seconds(visit["entry_time_sec"])
            for visit in state["visits"]
        ]
        stay_time_sec = sum(
            visit["stay_time_sec"]
            for visit in state["visits"]
        )
        visit_events = [
            {
                "event_index": event_index,
                "entry_time_sec": _round_seconds(visit["entry_time_sec"]),
                "exit_time_sec": (
                    _round_seconds(visit["exit_time_sec"])
                    if visit["exit_time_sec"] is not None
                    else None
                ),
                "stay_time_sec": _round_seconds(visit["stay_time_sec"]),
                "end_reason": visit["end_reason"],
            }
            for event_index, visit in enumerate(state["visits"], start=1)
        ]
        roi_results.append(
            {
                **roi.to_dict(),
                "approach_count": len(approach_times),
                "stay_time_sec": _round_seconds(stay_time_sec),
                "first_approach_time_sec": (
                    approach_times[0] if approach_times else None
                ),
                "approach_times_sec": approach_times,
                "visit_events": visit_events,
            }
        )

    return {
        "calculation_version": "roi-space-v2",
        "point_policy": "BBOX_CENTER",
        "settings": {
            "entry_confirmation_sec": float(settings.entry_confirmation_sec),
            "exit_confirmation_sec": float(settings.exit_confirmation_sec),
            "minimum_stay_sec": float(settings.minimum_stay_sec),
        },
        "roi_results": roi_results,
    }
