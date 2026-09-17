import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean

from baseline_policy import (
    AGGREGATION_SEC,
    ALL_CHANGE_STATUSES,
    FEATURE_NAMES,
    FEATURE_VERSION,
    INITIAL_CHANGE_STATUSES,
    MIN_COMPLETE_INTERVAL_COUNT,
    MIN_COMPLETE_INTERVAL_RATIO,
    SCHEMA_VERSION,
    UPDATE_CHANGE_STATUSES,
    VALID_ANALYSIS_STATUSES,
    VALID_QUALITY_STATUSES,
    BaselinePolicyError,
    assert_identity,
    calculate_daily_representative,
    identity_from_mapping,
    make_identity,
    parse_recorded_at,
    validate_identifier,
    validate_number,
)

SUPPORTED_ANALYSIS_SCHEMA_VERSIONS = {"1.1", "1.2"}


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
CSV_FEATURE_MAP = {
    "activity_level": "activity_level",
    "stationary_ratio": "stationary_ratio",
    "travel_distance": "normalized_travel_distance",
    "moving_speed": "normalized_moving_speed",
}


def resolve_project_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def load_json(path, error_label, error_code):
    if not path.exists():
        raise BaselinePolicyError(error_code, f"{error_label} 파일을 찾을 수 없습니다: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise BaselinePolicyError(error_code, f"{error_label} JSON 형식이 올바르지 않습니다.") from error
    except OSError as error:
        raise BaselinePolicyError(error_code, f"{error_label} 파일을 읽을 수 없습니다: {error}") from error
    if not isinstance(data, dict):
        raise BaselinePolicyError(error_code, f"{error_label} 최상위 값은 객체여야 합니다.")
    return data


def validate_analysis_result(data):
    required = (
        "schema_version", "analysis_id", "pet_id", "video_id", "camera_id",
        "analysis_status", "recorded_at", "aggregation_sec", "time_slot",
        "tracking_quality", "change_detection", "model_info", "video_info",
    )
    missing = [name for name in required if name not in data]
    if missing:
        raise BaselinePolicyError(
            "INVALID_ANALYSIS_RESULT", "필수 필드가 누락되었습니다: " + ", ".join(missing)
        )
    if data["schema_version"] not in SUPPORTED_ANALYSIS_SCHEMA_VERSIONS:
        raise BaselinePolicyError(
            "INVALID_ANALYSIS_RESULT",
            "분석 결과 schema_version은 1.1 또는 1.2여야 합니다.",
        )

    quality = data["tracking_quality"]
    change_detection = data["change_detection"]
    model_info = data["model_info"]
    video_info = data["video_info"]
    if not isinstance(quality, dict):
        raise BaselinePolicyError("INVALID_ANALYSIS_RESULT", "tracking_quality는 객체여야 합니다.")
    if not isinstance(change_detection, dict):
        raise BaselinePolicyError("INVALID_ANALYSIS_RESULT", "change_detection은 객체여야 합니다.")
    if not isinstance(model_info, dict):
        raise BaselinePolicyError("INVALID_ANALYSIS_RESULT", "model_info는 객체여야 합니다.")
    if not isinstance(video_info, dict) or not video_info.get("file_name"):
        raise BaselinePolicyError("INVALID_ANALYSIS_RESULT", "video_info.file_name이 누락되었습니다.")
    if model_info.get("feature_version") != FEATURE_VERSION:
        raise BaselinePolicyError(
            "INVALID_ANALYSIS_RESULT", f"model_info.feature_version은 {FEATURE_VERSION}이어야 합니다."
        )

    change_status = str(change_detection.get("change_status", "")).strip().upper()
    if change_status not in ALL_CHANGE_STATUSES:
        raise BaselinePolicyError("INVALID_ANALYSIS_RESULT", "change_status가 올바르지 않습니다.")
    aggregation_sec = validate_number(
        data["aggregation_sec"], "aggregation_sec", "INVALID_ANALYSIS_RESULT"
    )
    if aggregation_sec != AGGREGATION_SEC:
        raise BaselinePolicyError(
            "INVALID_ANALYSIS_RESULT", f"aggregation_sec은 {AGGREGATION_SEC}이어야 합니다."
        )
    identity = make_identity(data["pet_id"], data["camera_id"], data["time_slot"])
    return {
        **identity,
        "analysis_id": validate_identifier(data["analysis_id"], "analysis_id"),
        "video_id": validate_identifier(data["video_id"], "video_id"),
        "recorded_at": parse_recorded_at(data["recorded_at"]),
        "analysis_status": str(data["analysis_status"]).strip().upper(),
        "quality_status": str(quality.get("quality_status", "")).strip().upper(),
        "change_status": change_status,
        "video_stem": Path(video_info["file_name"]).stem,
    }


def get_pre_interval_skip(metadata, mode):
    if metadata["analysis_status"] not in VALID_ANALYSIS_STATUSES:
        return "SKIPPED_ANALYSIS_STATUS"
    if metadata["quality_status"] not in VALID_QUALITY_STATUSES:
        return "SKIPPED_TRACKING_QUALITY"
    allowed_changes = INITIAL_CHANGE_STATUSES if mode == "INITIAL" else UPDATE_CHANGE_STATUSES
    if metadata["change_status"] not in allowed_changes:
        return "SKIPPED_CHANGE_STATUS"
    return None


def load_representative_features(interval_csv, aggregation_sec):
    if not interval_csv.exists():
        raise BaselinePolicyError(
            "INVALID_ANALYSIS_RESULT", f"구간별 피처 CSV를 찾을 수 없습니다: {interval_csv}"
        )
    required = {*CSV_FEATURE_MAP, "analyzed_duration"}
    complete = []
    with interval_csv.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise BaselinePolicyError(
                "INVALID_ANALYSIS_RESULT", "구간별 피처 CSV 누락 컬럼: " + ", ".join(sorted(missing))
            )
        minimum_duration = aggregation_sec * MIN_COMPLETE_INTERVAL_RATIO
        for index, row in enumerate(reader, start=2):
            duration = validate_number(
                row["analyzed_duration"], f"{index}행 analyzed_duration", "INVALID_ANALYSIS_RESULT"
            )
            if duration < minimum_duration:
                continue
            complete.append(
                {
                    target: validate_number(row[source], target, "INVALID_ANALYSIS_RESULT")
                    for source, target in CSV_FEATURE_MAP.items()
                }
            )
    features = (
        {
            target: round(mean(row[target] for row in complete), 6)
            for target in FEATURE_NAMES
        }
        if complete else None
    )
    return features, len(complete)


def create_history(metadata):
    identity_keys = (
        "schema_version", "policy_version", "pet_id", "camera_id",
        "feature_version", "aggregation_sec", "time_slot", "reference_days",
    )
    return {
        **{key: metadata[key] for key in identity_keys},
        "minimum_complete_interval_count": MIN_COMPLETE_INTERVAL_COUNT,
        "daily_samples": [],
    }


def validate_history(history, metadata):
    actual_identity = identity_from_mapping(history, "INVALID_HISTORY_FORMAT")
    expected_identity = {key: metadata[key] for key in actual_identity}
    assert_identity(actual_identity, expected_identity, "BASELINE_HISTORY_MISMATCH")
    if history.get("minimum_complete_interval_count") != MIN_COMPLETE_INTERVAL_COUNT:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT",
            f"minimum_complete_interval_count는 {MIN_COMPLETE_INTERVAL_COUNT}이어야 합니다.",
        )
    if not isinstance(history.get("daily_samples"), list):
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", "daily_samples는 배열이어야 합니다.")


def update_history(history, metadata, features, complete_count):
    recorded_date = metadata["recorded_at"].date().isoformat()
    for daily in history["daily_samples"]:
        if not isinstance(daily, dict) or not isinstance(daily.get("analyses"), list):
            raise BaselinePolicyError("INVALID_HISTORY_FORMAT", "daily_samples 구조가 올바르지 않습니다.")
        for analysis in daily["analyses"]:
            if analysis.get("analysis_id") == metadata["analysis_id"]:
                return "DUPLICATE_ANALYSIS_SKIPPED", recorded_date

    target_day = next(
        (item for item in history["daily_samples"] if item.get("date") == recorded_date), None
    )
    is_new_date = target_day is None
    if target_day is None:
        target_day = {"date": recorded_date, "analyses": []}
        history["daily_samples"].append(target_day)

    target_day["analyses"].append(
        {
            "analysis_id": metadata["analysis_id"],
            "video_id": metadata["video_id"],
            "recorded_at": metadata["recorded_at"].isoformat(timespec="seconds"),
            "analysis_status": metadata["analysis_status"],
            "quality_status": metadata["quality_status"],
            "change_status": metadata["change_status"],
            "complete_interval_count": complete_count,
            "features": features,
        }
    )
    target_day["analyses"].sort(key=lambda item: (item["recorded_at"], item["analysis_id"]))
    target_day["representative"] = calculate_daily_representative(target_day["analyses"])
    history["daily_samples"].sort(key=lambda item: item["date"])
    status = "ADDED_NEW_DATE" if is_new_date else "ADDED_EXISTING_DATE_RECALCULATED"
    return status, recorded_date


def save_history(path, history):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2, allow_nan=False)
    temporary.replace(path)


def get_arguments():
    parser = argparse.ArgumentParser(description="Schema 1.1 분석 결과를 공식 Baseline history에 누적합니다.")
    parser.add_argument("analysis_result_json")
    parser.add_argument("--history-json", required=True)
    parser.add_argument("--interval-csv", default=None)
    parser.add_argument("--mode", required=True, choices=["INITIAL", "UPDATE"])
    return parser.parse_args()


def print_result(status, metadata, history_path, complete_count=None):
    print()
    print("=" * 60)
    print("BASELINE HISTORY UPDATE COMPLETE")
    print("=" * 60)
    print(f"Update Status  : {status}")
    print(f"Pet ID         : {metadata['pet_id']}")
    print(f"Camera ID      : {metadata['camera_id']}")
    print(f"Mode           : {metadata['mode']}")
    if complete_count is not None:
        print(f"Complete Slots : {complete_count}")
    print(f"History JSON   : {history_path}")
    print("=" * 60)


def main():
    args = get_arguments()
    result_path = resolve_project_path(args.analysis_result_json)
    history_path = resolve_project_path(args.history_json)
    result = load_json(result_path, "통합 분석 결과", "INVALID_ANALYSIS_RESULT")
    metadata = validate_analysis_result(result)
    metadata["mode"] = args.mode
    if args.mode == "UPDATE" and not history_path.exists():
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT",
            "UPDATE 모드에서는 기존 공식 Baseline history가 필요합니다.",
        )
    history = (
        load_json(history_path, "Baseline history", "INVALID_HISTORY_FORMAT")
        if history_path.exists() else None
    )
    if history is not None:
        validate_history(history, metadata)
    pre_skip = get_pre_interval_skip(metadata, args.mode)
    if pre_skip:
        print_result(pre_skip, metadata, history_path)
        return

    interval_path = (
        resolve_project_path(args.interval_csv)
        if args.interval_csv
        else OUTPUT_DIR / f"{metadata['video_stem']}_features_by_interval.csv"
    )
    features, complete_count = load_representative_features(interval_path, metadata["aggregation_sec"])
    if complete_count < MIN_COMPLETE_INTERVAL_COUNT:
        print_result(
            "SKIPPED_INSUFFICIENT_COMPLETE_INTERVALS", metadata, history_path, complete_count
        )
        return

    if history is None:
        history = create_history(metadata)
    status, _ = update_history(history, metadata, features, complete_count)
    if status in {"ADDED_NEW_DATE", "ADDED_EXISTING_DATE_RECALCULATED"}:
        save_history(history_path, history)
    print_result(status, metadata, history_path, complete_count)


def print_error(error):
    print()
    print("=" * 60)
    print("BASELINE HISTORY UPDATE FAILED")
    print("=" * 60)
    print(json.dumps({"error_code": error.code, "message": error.message}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BaselinePolicyError as error:
        print_error(error)
        sys.exit(1)
    except Exception as error:
        print_error(BaselinePolicyError("BASELINE_BUILD_ERROR", str(error)))
        sys.exit(1)
