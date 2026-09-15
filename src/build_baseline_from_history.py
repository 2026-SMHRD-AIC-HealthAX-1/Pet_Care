import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from baseline_policy import (
    FEATURE_NAMES,
    ALL_CHANGE_STATUSES,
    MIN_COMPLETE_INTERVAL_COUNT,
    REFERENCE_DAYS,
    VALID_ANALYSIS_STATUSES,
    VALID_QUALITY_STATUSES,
    BaselinePolicyError,
    assert_identity,
    calculate_baseline_features,
    calculate_daily_representative,
    identity_from_mapping,
    make_policy_prefix,
    parse_recorded_at,
    validate_feature_mapping,
    validate_identifier,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "baselines"
CSV_FEATURE_NAMES = {
    "activity_level": "activity_level",
    "stationary_ratio": "stationary_ratio",
    "normalized_travel_distance": "travel_distance",
    "normalized_moving_speed": "moving_speed",
}


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def resolve_project_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def load_json(path, error_code):
    if not path.exists():
        raise BaselinePolicyError(error_code, f"JSON 파일을 찾을 수 없습니다: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise BaselinePolicyError(error_code, f"JSON 파일을 읽을 수 없습니다: {path}") from error
    if not isinstance(data, dict):
        raise BaselinePolicyError(error_code, "최상위 JSON은 객체여야 합니다.")
    return data


def validate_analysis(analysis, location):
    if not isinstance(analysis, dict):
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"{location}은 객체여야 합니다.")
    required = (
        "analysis_id", "video_id", "recorded_at", "analysis_status",
        "quality_status", "change_status", "complete_interval_count", "features",
    )
    missing = [key for key in required if key not in analysis]
    if missing:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT", f"{location} 누락 필드: " + ", ".join(missing)
        )
    count = analysis["complete_interval_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < MIN_COMPLETE_INTERVAL_COUNT:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT",
            f"{location}.complete_interval_count는 {MIN_COMPLETE_INTERVAL_COUNT} 이상이어야 합니다.",
        )
    analysis_status = str(analysis["analysis_status"]).strip().upper()
    quality_status = str(analysis["quality_status"]).strip().upper()
    change_status = str(analysis["change_status"]).strip().upper()
    if analysis_status not in VALID_ANALYSIS_STATUSES:
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"{location}.analysis_status가 올바르지 않습니다.")
    if quality_status not in VALID_QUALITY_STATUSES:
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"{location}.quality_status가 올바르지 않습니다.")
    if change_status not in ALL_CHANGE_STATUSES:
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"{location}.change_status가 올바르지 않습니다.")
    parsed = dict(analysis)
    parsed["analysis_id"] = validate_identifier(
        analysis["analysis_id"], "analysis_id", "INVALID_HISTORY_FORMAT"
    )
    parsed["video_id"] = validate_identifier(
        analysis["video_id"], "video_id", "INVALID_HISTORY_FORMAT"
    )
    parsed["recorded_at"] = parse_recorded_at(
        analysis["recorded_at"], "INVALID_HISTORY_FORMAT"
    )
    parsed["features"] = validate_feature_mapping(
        analysis["features"], "INVALID_HISTORY_FORMAT"
    )
    return parsed


def validate_history(history):
    identity = identity_from_mapping(history, "INVALID_HISTORY_FORMAT")
    if history.get("minimum_complete_interval_count") != MIN_COMPLETE_INTERVAL_COUNT:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT",
            f"minimum_complete_interval_count는 {MIN_COMPLETE_INTERVAL_COUNT}이어야 합니다.",
        )
    daily_samples = history.get("daily_samples")
    if not isinstance(daily_samples, list):
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", "daily_samples는 배열이어야 합니다.")

    validated_days = []
    seen_dates = set()
    seen_analysis_ids = set()
    for day_index, day in enumerate(daily_samples):
        if not isinstance(day, dict):
            raise BaselinePolicyError("INVALID_HISTORY_FORMAT", "날짜 표본은 객체여야 합니다.")
        date_text = day.get("date")
        try:
            parsed_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except (TypeError, ValueError) as error:
            raise BaselinePolicyError(
                "INVALID_HISTORY_FORMAT", f"daily_samples[{day_index}].date가 올바르지 않습니다."
            ) from error
        if parsed_date in seen_dates:
            raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"중복 날짜가 있습니다: {date_text}")
        seen_dates.add(parsed_date)
        analyses = day.get("analyses")
        if not isinstance(analyses, list) or not analyses:
            raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"{date_text} analyses가 비어 있습니다.")
        validated_analyses = []
        for analysis_index, analysis in enumerate(analyses):
            validated = validate_analysis(
                analysis, f"daily_samples[{day_index}].analyses[{analysis_index}]"
            )
            analysis_id = validated["analysis_id"]
            if analysis_id in seen_analysis_ids:
                raise BaselinePolicyError("INVALID_HISTORY_FORMAT", f"중복 analysis_id: {analysis_id}")
            seen_analysis_ids.add(analysis_id)
            if validated["recorded_at"].date() != parsed_date:
                raise BaselinePolicyError(
                    "INVALID_HISTORY_FORMAT", f"{analysis_id}의 recorded_at 날짜가 date와 다릅니다."
                )
            validated_analyses.append(validated)
        representative = calculate_daily_representative(validated_analyses)
        stored_representative = day.get("representative")
        if stored_representative != representative:
            raise BaselinePolicyError(
                "INVALID_HISTORY_FORMAT", f"{date_text} representative가 analyses 재계산값과 다릅니다."
            )
        validated_days.append(
            {
                "date": parsed_date,
                "analyses": validated_analyses,
                "representative": representative,
            }
        )
    validated_days.sort(key=lambda item: item["date"])
    return identity, validated_days


def select_reference_days(daily_samples, reference_days=REFERENCE_DAYS):
    if len(daily_samples) < reference_days:
        raise BaselinePolicyError(
            "BASELINE_INSUFFICIENT_DATA",
            f"필요 일수: {reference_days}일, 현재 유효 일수: {len(daily_samples)}일",
        )
    return daily_samples[-reference_days:]


def validate_existing_baseline(path, identity):
    existing = load_json(path, "INVALID_BASELINE_FORMAT")
    actual_identity = identity_from_mapping(existing, "INVALID_BASELINE_FORMAT")
    assert_identity(actual_identity, identity, "BASELINE_IDENTITY_MISMATCH")
    revision = existing.get("baseline_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "baseline_revision이 올바르지 않습니다.")
    if not isinstance(existing.get("created_at"), str):
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "created_at이 누락되었습니다.")
    return existing


def validate_existing_csv(path, identity):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
    except OSError as error:
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "Baseline CSV를 읽을 수 없습니다.") from error
    required = {
        "schema_version", "policy_version", "pet_id", "camera_id",
        "feature_version", "aggregation_sec", "time_slot", "reference_days",
        "feature", "mean", "std",
    }
    if not rows or not required.issubset(set(reader.fieldnames or [])):
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "Baseline CSV 구조가 올바르지 않습니다.")
    for row in rows:
        try:
            csv_identity = {
                "schema_version": row["schema_version"],
                "policy_version": row["policy_version"],
                "pet_id": row["pet_id"],
                "camera_id": row["camera_id"],
                "feature_version": row["feature_version"],
                "aggregation_sec": float(row["aggregation_sec"]),
                "time_slot": row["time_slot"],
                "reference_days": int(row["reference_days"]),
            }
        except (TypeError, ValueError) as error:
            raise BaselinePolicyError(
                "INVALID_BASELINE_FORMAT", "Baseline CSV identity 값이 올바르지 않습니다."
            ) from error
        assert_identity(csv_identity, identity, "BASELINE_IDENTITY_MISMATCH")


def build_result(identity, selected_days, existing=None):
    timestamp = now_iso()
    source_analysis_count = sum(len(day["analyses"]) for day in selected_days)
    return {
        **identity,
        "source_date_count": len(selected_days),
        "source_analysis_count": source_analysis_count,
        "baseline_revision": 1 if existing is None else existing["baseline_revision"] + 1,
        "period_start": selected_days[0]["date"].isoformat(),
        "period_end": selected_days[-1]["date"].isoformat(),
        "created_at": timestamp if existing is None else existing["created_at"],
        "updated_at": timestamp,
        "features": calculate_baseline_features(selected_days),
    }


def default_output_paths(identity):
    prefix = make_policy_prefix(identity)
    return (
        DEFAULT_OUTPUT_DIR / f"{prefix}_baseline.json",
        DEFAULT_OUTPUT_DIR / f"{prefix}_baseline_features.csv",
    )


def save_results(result, json_path, csv_path):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_temp = json_path.with_suffix(json_path.suffix + ".tmp")
    csv_temp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with json_temp.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2, allow_nan=False)
    identity_fields = (
        "schema_version", "policy_version", "pet_id", "camera_id",
        "feature_version", "aggregation_sec", "time_slot", "reference_days",
    )
    with csv_temp.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[*identity_fields, "feature", "mean", "std"])
        writer.writeheader()
        for feature_name in FEATURE_NAMES:
            writer.writerow(
                {
                    **{key: result[key] for key in identity_fields},
                    "feature": CSV_FEATURE_NAMES[feature_name],
                    "mean": result["features"][feature_name]["mean"],
                    "std": result["features"][feature_name]["std"],
                }
            )
    csv_temp.replace(csv_path)
    json_temp.replace(json_path)


def get_arguments():
    parser = argparse.ArgumentParser(description="공식 Schema 1.1 history에서 Baseline을 생성·갱신합니다.")
    parser.add_argument("input_json")
    parser.add_argument("--mode", required=True, choices=["INITIAL", "UPDATE"])
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-csv", default=None)
    return parser.parse_args()


def main():
    args = get_arguments()
    history = load_json(resolve_project_path(args.input_json), "INVALID_HISTORY_FORMAT")
    identity, daily_samples = validate_history(history)
    selected_days = select_reference_days(daily_samples, identity["reference_days"])
    default_json, default_csv = default_output_paths(identity)
    json_path = resolve_project_path(args.output_json) if args.output_json else default_json
    csv_path = resolve_project_path(args.output_csv) if args.output_csv else default_csv
    json_exists = json_path.exists()
    csv_exists = csv_path.exists()
    if json_exists != csv_exists:
        raise BaselinePolicyError(
            "BASELINE_FILE_SET_INCOMPLETE", "Baseline JSON과 CSV는 항상 함께 존재해야 합니다."
        )
    if args.mode == "INITIAL" and (json_exists or csv_exists):
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "INITIAL 모드인데 Baseline이 이미 존재합니다.")
    if args.mode == "UPDATE" and not (json_exists and csv_exists):
        raise BaselinePolicyError("BASELINE_FILE_SET_INCOMPLETE", "UPDATE 모드에 필요한 Baseline이 없습니다.")
    existing = validate_existing_baseline(json_path, identity) if args.mode == "UPDATE" else None
    if args.mode == "UPDATE":
        validate_existing_csv(csv_path, identity)
    result = build_result(identity, selected_days, existing)
    save_results(result, json_path, csv_path)
    print()
    print("=" * 60)
    print("BASELINE BUILD COMPLETE")
    print("=" * 60)
    print(f"Mode              : {args.mode}")
    print(f"Pet ID            : {result['pet_id']}")
    print(f"Camera ID         : {result['camera_id']}")
    print(f"Reference Days    : {result['source_date_count']}")
    print(f"Source Analyses   : {result['source_analysis_count']}")
    print(f"Baseline Revision : {result['baseline_revision']}")
    print(f"Period            : {result['period_start']} ~ {result['period_end']}")
    print(f"JSON Output       : {json_path}")
    print(f"CSV Output        : {csv_path}")
    print("=" * 60)


def print_error(error):
    print()
    print("=" * 60)
    print("BASELINE BUILD FAILED")
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
