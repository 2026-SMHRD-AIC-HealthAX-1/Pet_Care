import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TEST_DIR = PROJECT_ROOT / "data" / "outputs" / "baseline_history_flow_test"
DEFAULT_HISTORY = PROJECT_ROOT / "data" / "inputs" / "PET-TEST-0001_08-00-09-00_history.json"
TEST_PET_ID = "PET-TEST-0001"
DAY_FACTORS = [0.96, 0.98, 0.99, 1.00, 1.01, 1.02, 1.04]
FEATURE_COLUMNS = [
    "activity_level",
    "stationary_ratio",
    "travel_distance",
    "moving_speed",
]


def resolve_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"통합 결과 JSON을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("통합 결과 JSON의 최상위 값은 객체여야 합니다.")
    return data


def load_interval_rows(path):
    if not path.exists():
        raise FileNotFoundError(f"구간별 피처 CSV를 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames or not rows:
        raise ValueError("구간별 피처 CSV가 비어 있습니다.")
    missing = set(FEATURE_COLUMNS + ["analyzed_duration"]) - set(fieldnames)
    if missing:
        raise ValueError(f"구간별 피처 CSV 누락 컬럼: {sorted(missing)}")
    return fieldnames, rows


def parse_datetime(value):
    normalized = str(value).strip()
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("recorded_at에는 타임존이 포함되어야 합니다.")
    return parsed


def create_test_analysis(source, recorded_at, day_number, video_name):
    result = dict(source)
    result["analysis_id"] = f"ANL-BASELINE-TEST-{day_number:02d}"
    result["video_id"] = f"VID-BASELINE-TEST-{day_number:02d}"
    result["pet_id"] = TEST_PET_ID
    result["analysis_status"] = "COMPLETED"
    result["recorded_at"] = recorded_at.isoformat(timespec="seconds")
    result["aggregation_sec"] = 5.0
    result["time_slot"] = "08:00-09:00"
    result["tracking_quality"] = dict(source.get("tracking_quality") or {})
    result["tracking_quality"]["quality_status"] = "GOOD"
    result["video_info"] = dict(source.get("video_info") or {})
    result["video_info"]["file_name"] = video_name
    return result


def create_test_interval_csv(path, fieldnames, source_rows, factor):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for source_row in source_rows:
            row = dict(source_row)
            for column in FEATURE_COLUMNS:
                value = float(row[column]) * factor
                if column in {"activity_level", "stationary_ratio"}:
                    value = min(1.0, value)
                row[column] = f"{value:.6f}"
            writer.writerow(row)


def run_checked(command, step_name):
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"{step_name} 실패 (종료 코드 {result.returncode})")


def get_arguments():
    parser = argparse.ArgumentParser(
        description="7일 베이스라인 이력 누적과 생성 흐름을 합성 데이터로 검증합니다."
    )
    parser.add_argument("analysis_result_json", help="기준으로 복제할 통합 결과 JSON")
    parser.add_argument("interval_csv", help="기준으로 복제할 구간별 피처 CSV")
    parser.add_argument(
        "--history-json",
        default=str(DEFAULT_HISTORY),
        help="테스트 이력을 저장할 경로",
    )
    return parser.parse_args()


def main():
    args = get_arguments()
    source_json_path = resolve_path(args.analysis_result_json)
    source_interval_path = resolve_path(args.interval_csv)
    history_path = resolve_path(args.history_json)
    updater = SRC_DIR / "update_baseline_history.py"
    builder = SRC_DIR / "build_baseline_from_history.py"
    for script in (updater, builder):
        if not script.exists():
            raise FileNotFoundError(f"필요한 스크립트를 찾을 수 없습니다: {script}")

    source = load_json(source_json_path)
    fieldnames, source_rows = load_interval_rows(source_interval_path)
    source_time = parse_datetime(source["recorded_at"])
    end_date = source_time.date()
    timezone_info = source_time.tzinfo
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("7-DAY BASELINE HISTORY FLOW TEST")
    print("=" * 60)
    print(f"Test Pet ID : {TEST_PET_ID}")
    print(f"History     : {history_path}")

    for index, factor in enumerate(DAY_FACTORS, start=1):
        test_date = end_date - timedelta(days=7 - index)
        recorded_at = datetime(
            test_date.year, test_date.month, test_date.day, 8, 30, tzinfo=timezone_info
        )
        video_name = f"baseline_test_day_{index:02d}.mp4"
        analysis_path = TEST_DIR / f"analysis_day_{index:02d}.json"
        interval_path = TEST_DIR / f"features_day_{index:02d}_by_interval.csv"
        test_analysis = create_test_analysis(source, recorded_at, index, video_name)
        with analysis_path.open("w", encoding="utf-8") as file:
            json.dump(test_analysis, file, ensure_ascii=False, indent=2, allow_nan=False)
        create_test_interval_csv(interval_path, fieldnames, source_rows, factor)
        run_checked(
            [
                sys.executable,
                str(updater),
                str(analysis_path),
                "--history-json",
                str(history_path),
                "--interval-csv",
                str(interval_path),
            ],
            f"{index}일차 이력 누적",
        )

    run_checked(
        [sys.executable, str(builder), str(history_path)],
        "7일 베이스라인 생성",
    )

    print()
    print("=" * 60)
    print("BASELINE HISTORY FLOW TEST COMPLETE")
    print("=" * 60)
    print("Valid Days     : 7 / 7")
    print("Baseline Ready : True")
    print(f"History JSON   : {history_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print()
        print("=" * 60)
        print("BASELINE HISTORY FLOW TEST FAILED")
        print("=" * 60)
        print(f"Error: {error}")
        sys.exit(1)
