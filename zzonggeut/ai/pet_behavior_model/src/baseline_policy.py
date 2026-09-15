import math
import re
from datetime import datetime
from statistics import mean, stdev


SCHEMA_VERSION = "1.1"
POLICY_VERSION = "baseline-policy-v1"
FEATURE_VERSION = "pet-features-v2.0"
AGGREGATION_SEC = 5.0
REFERENCE_DAYS = 7
MIN_COMPLETE_INTERVAL_COUNT = 5
MIN_COMPLETE_INTERVAL_RATIO = 0.90

FEATURE_NAMES = (
    "activity_level",
    "stationary_ratio",
    "normalized_travel_distance",
    "normalized_moving_speed",
)
VALID_ANALYSIS_STATUSES = {"COMPLETED", "COMPLETED_WITH_WARNING"}
VALID_QUALITY_STATUSES = {"GOOD", "WARNING"}
INITIAL_CHANGE_STATUSES = {"NOT_EVALUATED"}
UPDATE_CHANGE_STATUSES = {"NORMAL", "SLIGHT_CHANGE"}
ALL_CHANGE_STATUSES = {
    "NORMAL",
    "SLIGHT_CHANGE",
    "STRONG_CHANGE",
    "NOT_EVALUATED",
}
TIME_SLOT_PATTERN = re.compile(
    r"^(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d$"
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BaselinePolicyError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_recorded_at(value, error_code="INVALID_ANALYSIS_RESULT"):
    if not isinstance(value, str) or not value.strip():
        raise BaselinePolicyError(error_code, "recorded_at이 누락되었습니다.")
    normalized = value.strip()
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise BaselinePolicyError(
            error_code, "recorded_at은 ISO 8601 형식이어야 합니다."
        ) from error
    if parsed.tzinfo is None:
        raise BaselinePolicyError(
            error_code, "recorded_at에는 타임존이 포함되어야 합니다."
        )
    return parsed


def validate_number(value, name, error_code="INVALID_ANALYSIS_RESULT"):
    if isinstance(value, bool):
        raise BaselinePolicyError(error_code, f"{name}은 숫자여야 합니다.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise BaselinePolicyError(error_code, f"{name}은 숫자여야 합니다.") from error
    if not math.isfinite(number) or number < 0:
        raise BaselinePolicyError(
            error_code, f"{name}은 0 이상의 유한한 숫자여야 합니다."
        )
    if name in {"activity_level", "stationary_ratio"} and number > 1:
        raise BaselinePolicyError(error_code, f"{name}은 0~1 범위여야 합니다.")
    return number


def validate_identifier(value, name, error_code="INVALID_ANALYSIS_RESULT"):
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value.strip()):
        raise BaselinePolicyError(
            error_code,
            f"{name}은 영문 또는 숫자로 시작하는 128자 이하 식별자여야 합니다.",
        )
    return value.strip()


def validate_time_slot(value, error_code="INVALID_ANALYSIS_RESULT"):
    if not isinstance(value, str) or not TIME_SLOT_PATTERN.fullmatch(value.strip()):
        raise BaselinePolicyError(error_code, "time_slot은 HH:mm-HH:mm 형식이어야 합니다.")
    normalized = value.strip()
    start_time, end_time = normalized.split("-")
    if start_time == end_time:
        raise BaselinePolicyError(error_code, "time_slot 시작과 종료는 달라야 합니다.")
    return normalized


def safe_filename(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-")


def make_policy_prefix(identity):
    return "_".join(
        safe_filename(identity[key])
        for key in ("pet_id", "camera_id", "time_slot", "feature_version")
    ) + f"_{POLICY_VERSION}"


def make_identity(pet_id, camera_id, time_slot):
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "pet_id": validate_identifier(pet_id, "pet_id"),
        "camera_id": validate_identifier(camera_id, "camera_id"),
        "feature_version": FEATURE_VERSION,
        "aggregation_sec": AGGREGATION_SEC,
        "time_slot": validate_time_slot(time_slot),
        "reference_days": REFERENCE_DAYS,
    }


def identity_from_mapping(data, error_code="INVALID_HISTORY_FORMAT"):
    required = (
        "schema_version",
        "policy_version",
        "pet_id",
        "camera_id",
        "feature_version",
        "aggregation_sec",
        "time_slot",
        "reference_days",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise BaselinePolicyError(
            error_code, "identity 필드가 누락되었습니다: " + ", ".join(missing)
        )
    aggregation_sec = validate_number(data["aggregation_sec"], "aggregation_sec", error_code)
    reference_days = data["reference_days"]
    if isinstance(reference_days, bool) or not isinstance(reference_days, int):
        raise BaselinePolicyError(error_code, "reference_days는 정수여야 합니다.")
    return {
        "schema_version": str(data["schema_version"]).strip(),
        "policy_version": str(data["policy_version"]).strip(),
        "pet_id": validate_identifier(data["pet_id"], "pet_id", error_code),
        "camera_id": validate_identifier(data["camera_id"], "camera_id", error_code),
        "feature_version": str(data["feature_version"]).strip(),
        "aggregation_sec": aggregation_sec,
        "time_slot": validate_time_slot(data["time_slot"], error_code),
        "reference_days": reference_days,
    }


def assert_identity(actual, expected, error_code):
    mismatches = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: 기존={actual_value!r}, 요청={expected_value!r}")
    if mismatches:
        raise BaselinePolicyError(
            error_code, "identity가 일치하지 않습니다. " + "; ".join(mismatches)
        )


def validate_feature_mapping(features, error_code="INVALID_HISTORY_FORMAT"):
    if not isinstance(features, dict):
        raise BaselinePolicyError(error_code, "features는 객체여야 합니다.")
    missing = [name for name in FEATURE_NAMES if name not in features]
    if missing:
        raise BaselinePolicyError(
            error_code, "features 누락 항목: " + ", ".join(missing)
        )
    return {
        name: validate_number(features[name], name, error_code)
        for name in FEATURE_NAMES
    }


def calculate_daily_representative(analyses):
    if not analyses:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT", "날짜별 analyses가 비어 있습니다."
        )
    total_count = sum(int(item["complete_interval_count"]) for item in analyses)
    if total_count <= 0:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT", "완전 구간 합계는 0보다 커야 합니다."
        )
    features = {
        feature_name: round(
            sum(
                item["features"][feature_name]
                * int(item["complete_interval_count"])
                for item in analyses
            )
            / total_count,
            6,
        )
        for feature_name in FEATURE_NAMES
    }
    return {
        "method": "COMPLETE_INTERVAL_WEIGHTED_MEAN",
        "analysis_count": len(analyses),
        "total_complete_interval_count": total_count,
        "features": features,
    }


def calculate_baseline_features(daily_samples):
    if len(daily_samples) < 2:
        raise BaselinePolicyError(
            "BASELINE_INSUFFICIENT_DATA",
            "표준편차 계산을 위해 최소 2개의 날짜 대표값이 필요합니다.",
        )
    result = {}
    for feature_name in FEATURE_NAMES:
        values = [item["representative"]["features"][feature_name] for item in daily_samples]
        result[feature_name] = {
            "mean": round(mean(values), 6),
            "std": round(stdev(values), 6),
        }
    return result
