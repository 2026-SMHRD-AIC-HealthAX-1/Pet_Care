import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


ALLOWED_ROI_NAMES = {
    "FOOD_BOWL",
    "WATER_BOWL",
    "BED",
    "ETC",
}
ROI_TYPE_RECTANGLE = "RECTANGLE"
IDENTIFIER_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
)


class RoiValidationError(ValueError):
    """Raised when an ROI request does not satisfy the input contract."""


def _validate_identifier(value: Any, field_name: str) -> str:
    normalized = str(value).strip() if value is not None else ""
    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise RoiValidationError(
            f"{field_name} must start with an alphanumeric character, "
            "contain only letters, numbers, '.', '_' or '-', and be at "
            "most 128 characters."
        )
    return normalized


def _validate_ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoiValidationError(f"{field_name} must be a number.")

    normalized = float(value)
    if not math.isfinite(normalized):
        raise RoiValidationError(f"{field_name} must be finite.")
    if normalized < 0.0 or normalized > 1.0:
        raise RoiValidationError(f"{field_name} must be between 0 and 1.")
    return normalized


@dataclass(frozen=True)
class RectangleRoi:
    roi_id: str
    roi_name: str
    roi_type: str
    x: float
    y: float
    width: float
    height: float

    def contains(self, normalized_x: float, normalized_y: float) -> bool:
        """Return True for points inside the ROI, including its boundary."""
        return (
            self.x <= normalized_x <= self.x + self.width
            and self.y <= normalized_y <= self.y + self.height
        )

    def to_dict(self) -> dict:
        return {
            "roi_id": self.roi_id,
            "roi_name": self.roi_name,
            "roi_type": self.roi_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class RoiRequest:
    camera_id: str
    roi_areas: tuple[RectangleRoi, ...]


def _parse_roi_area(value: Any, index: int) -> RectangleRoi:
    if not isinstance(value, Mapping):
        raise RoiValidationError(f"roi_areas[{index}] must be an object.")

    roi_id = _validate_identifier(
        value.get("roi_id"),
        f"roi_areas[{index}].roi_id",
    )
    roi_name = str(value.get("roi_name", "")).strip().upper()
    if roi_name not in ALLOWED_ROI_NAMES:
        allowed = ", ".join(sorted(ALLOWED_ROI_NAMES))
        raise RoiValidationError(
            f"roi_areas[{index}].roi_name must be one of: {allowed}."
        )

    roi_type = str(value.get("roi_type", "")).strip().upper()
    if roi_type != ROI_TYPE_RECTANGLE:
        raise RoiValidationError(
            f"roi_areas[{index}].roi_type must be RECTANGLE."
        )

    x = _validate_ratio(value.get("x"), f"roi_areas[{index}].x")
    y = _validate_ratio(value.get("y"), f"roi_areas[{index}].y")
    width = _validate_ratio(
        value.get("width"),
        f"roi_areas[{index}].width",
    )
    height = _validate_ratio(
        value.get("height"),
        f"roi_areas[{index}].height",
    )

    if width <= 0.0 or height <= 0.0:
        raise RoiValidationError(
            f"roi_areas[{index}].width and height must be greater than 0."
        )
    if x + width > 1.0:
        raise RoiValidationError(f"roi_areas[{index}].x + width must be <= 1.")
    if y + height > 1.0:
        raise RoiValidationError(f"roi_areas[{index}].y + height must be <= 1.")

    return RectangleRoi(
        roi_id=roi_id,
        roi_name=roi_name,
        roi_type=roi_type,
        x=x,
        y=y,
        width=width,
        height=height,
    )


def parse_roi_request(
    value: Optional[Mapping[str, Any]],
    expected_camera_id: Optional[str] = None,
) -> Optional[RoiRequest]:
    """Validate an ROI request; missing and empty ROI lists normalize to None."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise RoiValidationError("ROI request must be an object.")

    camera_id = _validate_identifier(value.get("camera_id"), "camera_id")
    if expected_camera_id is not None:
        expected = _validate_identifier(expected_camera_id, "expected_camera_id")
        if camera_id != expected:
            raise RoiValidationError(
                "ROI camera_id does not match the analysis camera_id."
            )

    roi_areas: Any = value.get("roi_areas")
    if not isinstance(roi_areas, Sequence) or isinstance(
        roi_areas,
        (str, bytes, bytearray),
    ):
        raise RoiValidationError("roi_areas must be an array.")
    if not roi_areas:
        return None

    parsed = tuple(
        _parse_roi_area(area, index)
        for index, area in enumerate(roi_areas)
    )
    roi_ids = [area.roi_id for area in parsed]
    if len(roi_ids) != len(set(roi_ids)):
        raise RoiValidationError("roi_id values must be unique within a request.")

    return RoiRequest(camera_id=camera_id, roi_areas=parsed)
