import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
from jsonschema import Draft202012Validator, FormatChecker

from roi_models import RoiValidationError, parse_roi_request
from roi_space_analyzer import analyze_roi_usage, load_tracking_csv

from baseline_policy import (
    FEATURE_VERSION,
    POLICY_VERSION,
    BaselinePolicyError,
    assert_identity,
    identity_from_mapping,
    make_identity,
    make_policy_prefix,
)


# =========================================================
# 1. 프로젝트 경로
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent

SRC_DIR = BASE_DIR / "src"

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
)

INPUT_DIR = BASE_DIR / "data" / "inputs"
BASELINE_DIR = OUTPUT_DIR / "baselines"
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
SCHEMA_VERSION = "1.2"
PIPELINE_VERSION = "pet-behavior-v1.2"


# =========================================================
# 2. 실행 스크립트
# =========================================================
TRACK_SCRIPT = SRC_DIR / "track_pet.py"

FEATURE_SCRIPT = SRC_DIR / "extract_features.py"

CHANGE_SCRIPT = SRC_DIR / "detect_change.py"

JSON_SCRIPT = SRC_DIR / "generate_analysis_json.py"

HISTORY_SCRIPT = SRC_DIR / "update_baseline_history.py"

BASELINE_BUILD_SCRIPT = SRC_DIR / "build_baseline_from_history.py"
ROI_TEMP_DIR = OUTPUT_DIR / "analysis_results" / ".roi_tmp"


# =========================================================
# 3. Python 실행 환경
# =========================================================
PYTHON_EXECUTABLE = sys.executable
PIPELINE_CONTEXT = {}


class AnalysisIdConflictError(Exception):
    pass


# =========================================================
# 4. 공통 함수
# =========================================================
def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )


def parse_recorded_at(value):
    normalized = str(value).strip()

    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"

    try:
        recorded_time = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            "recorded_at은 ISO 8601 형식이어야 합니다. "
            "예: 2026-09-10T08:30:00+09:00"
        ) from error

    if recorded_time.tzinfo is None:
        raise ValueError(
            "recorded_at에는 타임존이 포함되어야 합니다. "
            "예: 2026-09-10T08:30:00+09:00"
        )

    return recorded_time


def make_time_slot(reference_time=None):
    current_time = reference_time or datetime.now().astimezone()

    start_hour = current_time.hour
    end_hour = (start_hour + 1) % 24

    return (
        f"{start_hour:02d}:00-"
        f"{end_hour:02d}:00"
    )


def parse_time_slot(value):
    normalized = str(value).strip()
    match = re.fullmatch(
        r"([01]\d|2[0-3]):00-([01]\d|2[0-3]):00",
        normalized,
    )

    if match is None:
        raise ValueError(
            "time_slot은 HH:00-HH:00 형식이어야 합니다. "
            "예: 08:00-09:00"
        )

    start_hour = int(match.group(1))
    end_hour = int(match.group(2))

    if end_hour != (start_hour + 1) % 24:
        raise ValueError(
            "time_slot은 연속된 1시간 구간이어야 합니다. "
            "예: 08:00-09:00 또는 23:00-00:00"
        )

    return normalized


def make_path_argument(target_path):
    """프로젝트 내부 파일은 상대 경로로 변환한다."""
    try:
        return str(
            target_path.relative_to(BASE_DIR)
        )

    except ValueError:
        return str(target_path)


def resolve_path(input_path):
    """입력받은 상대·절대 경로를 프로젝트 기준 절대 경로로 변환한다."""
    path = Path(input_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


def validate_video_file(video_path):
    extension = video_path.suffix.lower()

    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise ValueError(
            "지원하지 않는 영상 형식입니다. "
            f"입력 확장자: {extension or '(없음)'}, "
            f"허용 확장자: {supported}"
        )

    capture = cv2.VideoCapture(str(video_path))

    try:
        opened = capture.isOpened()
        frame_read, frame = capture.read() if opened else (False, None)
    finally:
        capture.release()

    if not opened or not frame_read or frame is None:
        raise ValueError(
            "영상 파일을 열거나 첫 프레임을 읽을 수 없습니다.\n"
            f"확인 경로: {video_path}"
        )


def safe_filename(value):
    return re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        str(value).strip(),
    ).strip("-")


def derive_baseline_json_path(csv_path):
    name = csv_path.name
    suffix = "_baseline_features.csv"
    if name.endswith(suffix):
        return csv_path.with_name(name[:-len(suffix)] + "_baseline.json")
    return csv_path.with_suffix(".json")


def file_digest(path):
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_baseline_file_set(json_path, csv_path, expected_identity):
    json_exists = json_path.is_file()
    csv_exists = csv_path.is_file()
    if json_exists != csv_exists:
        raise BaselinePolicyError(
            "BASELINE_FILE_SET_INCOMPLETE",
            "Baseline JSON과 CSV는 항상 함께 존재해야 합니다.",
        )
    if not json_exists:
        return False
    try:
        with json_path.open("r", encoding="utf-8-sig") as file:
            metadata = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise BaselinePolicyError(
            "INVALID_BASELINE_FORMAT", "Baseline JSON을 읽을 수 없습니다."
        ) from error
    if not isinstance(metadata, dict):
        raise BaselinePolicyError("INVALID_BASELINE_FORMAT", "Baseline JSON은 객체여야 합니다.")
    actual_identity = identity_from_mapping(metadata, "INVALID_BASELINE_FORMAT")
    assert_identity(actual_identity, expected_identity, "BASELINE_IDENTITY_MISMATCH")
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
    except OSError as error:
        raise BaselinePolicyError(
            "INVALID_BASELINE_FORMAT", "Baseline CSV를 읽을 수 없습니다."
        ) from error
    required_columns = {
        "schema_version", "policy_version", "pet_id", "camera_id",
        "feature_version", "aggregation_sec", "time_slot", "reference_days",
        "feature", "mean", "std",
    }
    if not rows or not required_columns.issubset(set(reader.fieldnames or [])):
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
        assert_identity(csv_identity, expected_identity, "BASELINE_IDENTITY_MISMATCH")
    return True


def classify_pipeline_error(error, step_name):
    message = str(error).lower()

    if isinstance(error, FileNotFoundError):
        return "VIDEO_NOT_FOUND" if step_name == "INPUT" else "ANALYSIS_ERROR"

    if "지원하지" in message and "영상" in message:
        return "UNSUPPORTED_VIDEO_FORMAT"

    if "영상" in message and ("열" in message or "읽" in message):
        return "VIDEO_READ_ERROR"

    if step_name == "INPUT":
        return "INVALID_REQUEST"

    if "검출" in message and ("없" in message or "못" in message):
        return "PET_NOT_DETECTED"

    return "ANALYSIS_ERROR"


def build_failed_result(inputs, started_at, error_code, message):
    completed_at = now_iso()

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": inputs["analysis_id"],
        "pet_id": inputs["pet_id"],
        "video_id": inputs["video_id"],
        "camera_id": inputs["camera_id"],
        "species": inputs["pet_type"].upper(),
        "analysis_status": "FAILED",
        "recorded_at": inputs["recorded_at"],
        "recorded_at_source": inputs["recorded_at_source"],
        "aggregation_sec": 5.0,
        "time_slot": inputs["time_slot"],
        "started_at": started_at,
        "completed_at": completed_at,
        "video_info": None,
        "tracking_quality": None,
        "features_overall": None,
        "features_by_interval": [],
        "baseline_comparison": [],
        "change_detection": {
            "baseline_status": "NOT_READY",
            "change_score": None,
            "change_status": "NOT_EVALUATED",
            "evaluated_feature_count": 0,
            "threshold_exceeded_count": 0,
            "contributing_factors": [],
        },
        "space_analysis": None,
        "model_info": {
            "pipeline_version": PIPELINE_VERSION,
            "feature_version": FEATURE_VERSION,
            "detector": "YOLO11s",
            "movement_window_sec": 1.0,
            "movement_threshold": 0.04,
            "aggregation_sec": 5.0,
            "std_zero_policy": "EXCLUDE_FEATURE",
        },
        "warnings": [],
        "error": {
            "code": error_code,
            "message": str(message).strip() or "분석 중 오류가 발생했습니다.",
        },
    }


def save_failed_result(inputs, started_at, error_code, message):
    result = build_failed_result(
        inputs,
        started_at,
        error_code,
        message,
    )

    schema_path = BASE_DIR / "schemas" / "analysis_result_v1.2.schema.json"

    with schema_path.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(result),
        key=lambda item: list(item.absolute_path),
    )

    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"실패 결과 JSON Schema 검증 실패: {details}")

    result_dir = OUTPUT_DIR / "analysis_results"
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / f"{inputs['analysis_id']}_result.json"
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )

    temporary_path.replace(output_path)
    return output_path


def find_existing_analysis_result(inputs):
    output_path = (
        OUTPUT_DIR
        / "analysis_results"
        / f"{inputs['analysis_id']}_result.json"
    )

    if not output_path.exists():
        return None

    try:
        with output_path.open("r", encoding="utf-8-sig") as file:
            existing = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisIdConflictError(
            "동일 analysis_id의 기존 결과 파일을 정상적으로 읽을 수 없습니다. "
            f"기존 파일을 보호하기 위해 분석을 중단합니다: {output_path}"
        ) from error

    expected = {
        "analysis_id": inputs["analysis_id"],
        "pet_id": inputs["pet_id"],
        "video_id": inputs["video_id"],
        "camera_id": inputs["camera_id"],
        "species": inputs["pet_type"].upper(),
    }
    mismatches = []

    for key, value in expected.items():
        if existing.get(key) != value:
            mismatches.append(
                f"{key}: 기존={existing.get(key)!r}, 요청={value!r}"
            )

    requested_roi = inputs.get("roi_request")
    requested_roi_config = (
        [area.to_dict() for area in requested_roi.roi_areas]
        if requested_roi is not None
        else None
    )
    existing_space = existing.get("space_analysis")
    existing_roi_config = None
    if isinstance(existing_space, dict):
        roi_results = existing_space.get("roi_results")
        if isinstance(roi_results, list):
            existing_roi_config = [
                {
                    key: item.get(key)
                    for key in (
                        "roi_id", "roi_name", "roi_type",
                        "x", "y", "width", "height",
                    )
                }
                for item in roi_results
                if isinstance(item, dict)
            ]

    if existing_roi_config != requested_roi_config:
        mismatches.append(
            "roi_areas: 기존 ROI 설정과 현재 요청 ROI 설정이 다릅니다."
        )

    if mismatches:
        raise AnalysisIdConflictError(
            "동일 analysis_id가 다른 분석 정보에 이미 사용되었습니다. "
            "기존 결과는 덮어쓰지 않습니다. "
            + "; ".join(mismatches)
        )

    return output_path


# =========================================================
# 5. 명령행 입력
# =========================================================
def get_pipeline_inputs():
    parser = argparse.ArgumentParser(
        description=(
            "반려동물 행동 분석 전체 파이프라인\n"
            "Tracking → Feature → Change Detection → JSON"
        )
    )

    parser.add_argument(
        "current_video",
        help="현재 분석할 영상 경로",
    )

    parser.add_argument(
        "pet_type",
        help="등록된 반려동물 종: cat 또는 dog",
    )

    parser.add_argument(
        "baseline_csv",
        nargs="?",
        default=None,
        help=(
            "build_baseline_from_history.py로 생성한 "
            "Baseline Feature CSV 경로. 생략 시 pet_id와 time_slot로 자동 탐색"
        ),
    )

    parser.add_argument(
        "--history-json",
        default=None,
        help="Baseline 이력 JSON 경로. 생략 시 pet_id와 time_slot로 자동 생성",
    )

    parser.add_argument(
        "--baseline-json",
        default=None,
        help="Baseline 메타데이터 JSON 경로. 생략 시 CSV 경로에서 자동 결정",
    )

    # 현재는 로컬 통합 테스트용 식별자다.
    # 실제 모델 API 연동 시 백엔드가 생성한 값을 전달한다.
    parser.add_argument(
        "--analysis-id",
        default=None,
        help="분석 ID",
    )

    parser.add_argument(
        "--pet-id",
        default=None,
        help="반려동물 ID",
    )

    parser.add_argument(
        "--video-id",
        default=None,
        help="영상 ID",
    )

    parser.add_argument(
        "--camera-id",
        required=True,
        help="카메라 ID",
    )

    parser.add_argument(
        "--recorded-at",
        default=None,
        help="촬영 시각. 예: 2026-09-08T09:00:00+09:00",
    )

    parser.add_argument(
        "--recorded-at-source",
        default="REQUEST_TIME",
        help="촬영 시각 출처: CAMERA, FILE_METADATA 또는 REQUEST_TIME",
    )

    parser.add_argument(
        "--roi-request-json",
        default=None,
        help="선택적 ROI 요청 JSON 파일 경로",
    )

    parser.add_argument(
        "--time-slot",
        default=None,
        help="베이스라인 비교 시간대. 예: 09:00-10:00",
    )

    parser.add_argument(
        "--precomputed-live",
        action="store_true",
        help="LIVE에서 이미 생성한 Tracking/Feature 산출물을 재사용",
    )

    args = parser.parse_args()

    current_video_path = resolve_path(
        args.current_video
    )

    run_timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    requested_pet_type = str(args.pet_type).strip().lower()
    input_error = None

    if requested_pet_type not in {"cat", "dog"}:
        pet_type = "unknown"
        input_error = (
            "pet_type은 cat 또는 dog만 지원합니다. "
            f"입력값: {args.pet_type!r}"
        )
    else:
        pet_type = requested_pet_type

    requested_recorded_at_source = str(
        args.recorded_at_source
    ).strip().upper()
    allowed_recorded_at_sources = {
        "CAMERA",
        "FILE_METADATA",
        "REQUEST_TIME",
    }

    if requested_recorded_at_source not in allowed_recorded_at_sources:
        recorded_at_source = "REQUEST_TIME"
        if input_error is None:
            input_error = (
                "recorded_at_source는 CAMERA, FILE_METADATA 또는 "
                "REQUEST_TIME만 허용합니다. "
                f"입력값: {args.recorded_at_source!r}"
            )
    else:
        recorded_at_source = requested_recorded_at_source

    invalid_identifiers = []

    def normalize_identifier(value, field_name, default_value):
        if value is None:
            return default_value

        normalized = str(value).strip()
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
            normalized,
        ):
            invalid_identifiers.append(field_name)
            return default_value

        return normalized

    analysis_id = normalize_identifier(
        args.analysis_id,
        "analysis_id",
        f"ANL-LOCAL-{run_timestamp}",
    )
    pet_id = normalize_identifier(
        args.pet_id,
        "pet_id",
        f"PET-LOCAL-{pet_type.upper()}",
    )
    video_id = normalize_identifier(
        args.video_id,
        "video_id",
        f"VID-LOCAL-{run_timestamp}",
    )
    camera_id = normalize_identifier(
        args.camera_id,
        "camera_id",
        "CAMERA-INVALID",
    )

    if invalid_identifiers and input_error is None:
        input_error = (
            "식별자는 영문 또는 숫자로 시작하고, 영문·숫자·점(.)·"
            "밑줄(_)·하이픈(-)만 사용할 수 있으며 128자 이하여야 합니다. "
            "잘못된 필드: " + ", ".join(invalid_identifiers)
        )

    recorded_at = args.recorded_at or now_iso()

    try:
        recorded_time = parse_recorded_at(recorded_at)
    except ValueError as error:
        # 실패 JSON도 Schema를 통과해야 하므로 잘못된 원본 문자열 대신
        # 요청 처리 시각을 기록하고, 실제 입력 오류는 error.message에 남긴다.
        recorded_time = parse_recorded_at(now_iso())
        if input_error is None:
            input_error = str(error)

    if args.time_slot:
        try:
            time_slot = parse_time_slot(args.time_slot)
        except ValueError as error:
            time_slot = make_time_slot(recorded_time)
            if input_error is None:
                input_error = str(error)
    else:
        time_slot = make_time_slot(recorded_time)
    policy_identity = make_identity(pet_id, camera_id, time_slot)
    prefix = make_policy_prefix(policy_identity)

    baseline_csv_path = (
        resolve_path(args.baseline_csv)
        if args.baseline_csv
        else (BASELINE_DIR / f"{prefix}_baseline_features.csv").resolve()
    )
    baseline_json_path = (
        resolve_path(args.baseline_json)
        if args.baseline_json
        else derive_baseline_json_path(baseline_csv_path)
    )
    history_json_path = (
        resolve_path(args.history_json)
        if args.history_json
        else (INPUT_DIR / f"{prefix}_history.json").resolve()
    )

    roi_request_path = (
        resolve_path(args.roi_request_json)
        if args.roi_request_json
        else None
    )
    roi_request = None
    if roi_request_path is not None:
        try:
            with roi_request_path.open("r", encoding="utf-8-sig") as file:
                roi_raw = json.load(file)
            roi_request = parse_roi_request(
                roi_raw,
                expected_camera_id=camera_id,
            )
        except (OSError, json.JSONDecodeError, RoiValidationError) as error:
            if input_error is None:
                input_error = f"ROI 요청이 올바르지 않습니다: {error}"

    return {
        "current_video_path": current_video_path,
        "baseline_csv_path": baseline_csv_path,
        "baseline_json_path": baseline_json_path,
        "history_json_path": history_json_path,
        "baseline_identity": policy_identity,
        "pet_type": pet_type,
        "analysis_id": analysis_id,
        "pet_id": pet_id,
        "video_id": video_id,
        "camera_id": camera_id,
        "recorded_at": recorded_time.isoformat(
            timespec="seconds"
        ),
        "recorded_at_source": recorded_at_source,
        "time_slot": time_slot,
        "roi_request_path": roi_request_path,
        "roi_request": roi_request,
        "input_error": input_error,
        "precomputed_live": args.precomputed_live,
    }


# =========================================================
# 6. 개별 단계 실행
# =========================================================
def run_step(
    step_number,
    step_name,
    script_path,
    arguments=None,
):
    print()
    print("=" * 60)
    print(f"STEP {step_number} - {step_name}")
    print("=" * 60)

    if not script_path.exists():
        raise FileNotFoundError(
            "실행 파일을 찾을 수 없습니다.\n"
            f"{script_path}"
        )

    command = [
        PYTHON_EXECUTABLE,
        str(script_path),
    ]

    if arguments:
        command.extend(arguments)

    print("Command:")
    print(" ".join(command))

    start_time = time.time()

    result = subprocess.run(
        command,
        cwd=BASE_DIR,
    )

    elapsed_time = time.time() - start_time

    if result.returncode != 0:
        print()
        print(f"[FAILED] {step_name}")
        print(f"Return Code : {result.returncode}")

        raise RuntimeError(
            f"{step_name} 단계에서 오류가 발생했습니다."
        )

    print()
    print(f"[SUCCESS] {step_name}")
    print(f"Elapsed Time : {elapsed_time:.2f} sec")


# =========================================================
# 7. Tracking 품질 결과 읽기
# =========================================================
def load_tracking_quality(quality_path):
    if not quality_path.exists():
        raise FileNotFoundError(
            "Tracking 품질 파일을 찾을 수 없습니다.\n"
            f"{quality_path}"
        )

    with open(
        quality_path,
        "r",
        encoding="utf-8",
    ) as csvfile:
        rows = list(
            csv.DictReader(csvfile)
        )

    if not rows:
        raise ValueError(
            "Tracking 품질 CSV에 데이터가 없습니다."
        )

    row = rows[0]

    analysis_allowed = (
        row["analysis_allowed"]
        .strip()
        .lower()
        == "true"
    )

    return {
        "video": row["video"],
        "raw_detected_frames": int(float(row["raw_detected_frames"])),
        "detection_rate": float(
            row["detection_rate"]
        ),
        "interpolation_ratio": float(
            row["interpolation_ratio"]
        ),
        "missing_ratio": float(
            row["missing_ratio"]
        ),
        "tracking_quality": row["tracking_quality"],
        "analysis_allowed": analysis_allowed,
    }


def print_tracking_quality(quality):
    print()
    print("=" * 60)
    print("STEP 2 - TRACKING QUALITY CHECK")
    print("=" * 60)

    print(f"Video               : {quality['video']}")

    print(
        "Detection Rate      : "
        f"{quality['detection_rate'] * 100:.2f}%"
    )

    print(
        "Interpolation Ratio : "
        f"{quality['interpolation_ratio'] * 100:.2f}%"
    )

    print(
        "Missing Ratio       : "
        f"{quality['missing_ratio'] * 100:.2f}%"
    )

    print(
        "Tracking Quality    : "
        f"{quality['tracking_quality']}"
    )

    print(
        "Analysis Allowed    : "
        f"{quality['analysis_allowed']}"
    )


# =========================================================
# 8. 결과 파일 경로
# =========================================================
def get_result_paths(
    current_video_path,
    baseline_csv_path,
    analysis_id,
):
    current_name = current_video_path.stem
    change_detail_path = (
        OUTPUT_DIR
        / f"{current_name}_change_detection.csv"
    )

    change_summary_path = (
        OUTPUT_DIR
        / f"{current_name}_change_summary.csv"
    )

    return {
        "tracking": (
            OUTPUT_DIR
            / f"{current_name}_tracking.csv"
        ),
        "quality": (
            OUTPUT_DIR
            / f"{current_name}_tracking_quality.csv"
        ),
        "features": (
            OUTPUT_DIR
            / f"{current_name}_features.csv"
        ),
        "interval_features": (
            OUTPUT_DIR
            / f"{current_name}_features_by_interval.csv"
        ),
        "baseline": baseline_csv_path,
        "change_detail": change_detail_path,
        "change_summary": change_summary_path,
        "analysis_result": (
            OUTPUT_DIR
            / "analysis_results"
            / f"{analysis_id}_result.json"
        ),
    }


# =========================================================
# 9. Baseline 이력 상태 확인
# =========================================================
def is_history_ready(history_path):
    if not history_path.exists():
        return False

    with history_path.open("r", encoding="utf-8-sig") as file:
        history = json.load(file)

    identity_from_mapping(history, "INVALID_HISTORY_FORMAT")
    if history.get("policy_version") != POLICY_VERSION:
        raise BaselinePolicyError(
            "INVALID_HISTORY_FORMAT", "지원하지 않는 Baseline policy_version입니다."
        )
    daily_samples = history.get("daily_samples")
    if not isinstance(daily_samples, list):
        raise BaselinePolicyError("INVALID_HISTORY_FORMAT", "daily_samples는 배열이어야 합니다.")
    unique_dates = {
        item.get("date")
        for item in daily_samples
        if isinstance(item, dict) and item.get("date")
    }
    return len(unique_dates) >= int(history["reference_days"])


# =========================================================
# 10. 전체 파이프라인
# =========================================================
def main():
    global PIPELINE_CONTEXT

    pipeline_start = time.time()
    pipeline_started_at = now_iso()

    inputs = get_pipeline_inputs()
    PIPELINE_CONTEXT = {
        "inputs": inputs,
        "started_at": pipeline_started_at,
        "step_name": "INPUT",
    }

    if inputs["input_error"]:
        raise ValueError(inputs["input_error"])

    if not inputs["current_video_path"].is_file():
        raise FileNotFoundError(
            "현재 분석 영상을 찾을 수 없습니다.\n"
            f"{inputs['current_video_path']}"
        )

    validate_video_file(inputs["current_video_path"])

    current_video_path = inputs["current_video_path"]
    baseline_csv_path = inputs["baseline_csv_path"]
    baseline_json_path = inputs["baseline_json_path"]
    history_json_path = inputs["history_json_path"]
    pet_type = inputs["pet_type"]
    baseline_available = validate_baseline_file_set(
        baseline_json_path,
        baseline_csv_path,
        inputs["baseline_identity"],
    )

    current_video_argument = make_path_argument(
        current_video_path
    )

    baseline_csv_argument = make_path_argument(
        baseline_csv_path
    )

    result_paths = get_result_paths(
        current_video_path,
        baseline_csv_path,
        inputs["analysis_id"],
    )

    existing_result_path = find_existing_analysis_result(inputs)

    if existing_result_path is not None:
        print()
        print("=" * 60)
        print("DUPLICATE ANALYSIS REQUEST")
        print("=" * 60)
        print(f"Analysis ID    : {inputs['analysis_id']}")
        print("Action         : EXISTING_RESULT_REUSED")
        print(f"Existing JSON  : {existing_result_path}")
        print("Tracking과 이후 분석 단계는 다시 실행하지 않습니다.")
        print("=" * 60)
        return

    print()
    print("=" * 60)
    print("PET BEHAVIOR ANALYSIS PIPELINE")
    print("=" * 60)

    print(f"Current Video  : {current_video_path.name}")
    print(f"Registered Pet : {pet_type}")
    print(f"Baseline CSV   : {baseline_csv_path.name}")
    print(f"Baseline JSON  : {baseline_json_path.name}")
    print(
        "Baseline Status: "
        + ("READY" if baseline_available else "NOT_READY")
    )
    print(f"History JSON   : {history_json_path.name}")
    print(f"Analysis ID    : {inputs['analysis_id']}")
    print(f"Pet ID         : {inputs['pet_id']}")
    print(f"Video ID       : {inputs['video_id']}")
    print(f"Camera ID      : {inputs['camera_id']}")
    print(f"Feature Version: {FEATURE_VERSION}")

    # LIVE는 push_frame()에서 이미 Tracking을 수행했으므로 이중 YOLO를 피한다.
    if not inputs["precomputed_live"]:
        PIPELINE_CONTEXT["step_name"] = "TRACKING"
        run_step(1, "PET TRACKING", TRACK_SCRIPT, [current_video_argument, pet_type])
    else:
        for required in (result_paths["tracking"], result_paths["quality"],
                         result_paths["features"], result_paths["interval_features"]):
            if not required.is_file():
                raise FileNotFoundError(f"LIVE 사전 계산 산출물이 없습니다: {required}")

    # -----------------------------------------------------
    # STEP 2. Tracking 품질 검사
    # -----------------------------------------------------
    quality = load_tracking_quality(
        result_paths["quality"]
    )

    print_tracking_quality(quality)

    if not quality["analysis_allowed"]:
        total_time = time.time() - pipeline_start
        error_code = (
            "PET_NOT_DETECTED"
            if quality["raw_detected_frames"] == 0
            else "INSUFFICIENT_TRACKING"
        )
        error_message = (
            "분석 대상 반려동물을 검출하지 못했습니다."
            if error_code == "PET_NOT_DETECTED"
            else "유효 추적 데이터가 기준보다 부족합니다."
        )
        output_path = save_failed_result(
            inputs,
            pipeline_started_at,
            error_code,
            error_message,
        )

        print()
        print("=" * 60)
        print("PIPELINE STOPPED")
        print("=" * 60)

        print(
            "Tracking 품질이 낮아 "
            "Feature 추출 이후 단계를 진행하지 않습니다."
        )

        print(
            f"Tracking Quality : "
            f"{quality['tracking_quality']}"
        )

        print(
            f"Total Time       : "
            f"{total_time:.2f} sec"
        )

        print(f"Failure JSON    : {output_path}")

        sys.exit(1)

    # STEP 2.5. ROI는 LIVE에서도 누적 Tracking을 재사용해 동일 계약으로 확정한다.
    roi_temp_path = None
    if inputs["roi_request"] is not None:
        PIPELINE_CONTEXT["step_name"] = "ROI_SPACE_ANALYSIS"
        capture = cv2.VideoCapture(str(current_video_path))
        try:
            frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            capture.release()
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("ROI 분석용 영상 너비/높이를 읽을 수 없습니다.")

        tracking_rows = load_tracking_csv(result_paths["tracking"])
        space_analysis = analyze_roi_usage(
            tracking_rows,
            inputs["roi_request"],
            frame_width,
            frame_height,
        )
        ROI_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        roi_temp_path = ROI_TEMP_DIR / f"{inputs['analysis_id']}_space_analysis.json"
        with roi_temp_path.open("w", encoding="utf-8") as file:
            json.dump(space_analysis, file, ensure_ascii=False, indent=2, allow_nan=False)

    if not inputs["precomputed_live"]:
        PIPELINE_CONTEXT["step_name"] = "FEATURE_EXTRACTION"
        run_step(3, "ROLLING FEATURE EXTRACTION", FEATURE_SCRIPT, [current_video_argument])

    # -----------------------------------------------------
    # STEP 4. 변화 감지
    # -----------------------------------------------------
    if baseline_available:
        PIPELINE_CONTEXT["step_name"] = "CHANGE_DETECTION"
        run_step(
            4,
            "CHANGE DETECTION",
            CHANGE_SCRIPT,
            [
                current_video_argument,
                baseline_csv_argument,
            ],
        )
        change_detail_for_json = result_paths["change_detail"]
        change_summary_for_json = result_paths["change_summary"]
        change_step_status = "COMPLETE"

    else:
        print()
        print("=" * 60)
        print("STEP 4 - CHANGE DETECTION SKIPPED")
        print("=" * 60)
        print("Baseline이 아직 준비되지 않아 변화 감지를 건너뜁니다.")
        print("현재 분석 결과는 Baseline 이력에 누적됩니다.")

        # 같은 영상명의 과거 변화 CSV가 남아 있어도 재사용하지 않는다.
        pending_dir = OUTPUT_DIR / "analysis_results" / "pending_change"
        change_detail_for_json = (
            pending_dir
            / f"{inputs['analysis_id']}_change_detection.csv"
        )
        change_summary_for_json = (
            pending_dir
            / f"{inputs['analysis_id']}_change_summary.csv"
        )
        change_step_status = "NOT_EVALUATED"

    # -----------------------------------------------------
    # STEP 5. 통합 JSON 생성 및 Schema 검증
    # -----------------------------------------------------
    PIPELINE_CONTEXT["step_name"] = "JSON_GENERATION"
    json_arguments = [
        "--video",
        current_video_argument,
        "--species",
        pet_type.upper(),
        "--analysis-id",
        inputs["analysis_id"],
        "--pet-id",
        inputs["pet_id"],
        "--video-id",
        inputs["video_id"],
        "--camera-id",
        inputs["camera_id"],
        "--recorded-at",
        inputs["recorded_at"],
        "--recorded-at-source",
        inputs["recorded_at_source"],
        "--time-slot",
        inputs["time_slot"],
        "--started-at",
        pipeline_started_at,
        "--change-detail-csv",
        str(change_detail_for_json),
        "--change-summary-csv",
        str(change_summary_for_json),
    ]
    if roi_temp_path is not None:
        json_arguments.extend([
            "--space-analysis-json",
            make_path_argument(roi_temp_path),
        ])

    run_step(
        5,
        "INTEGRATED RESULT JSON GENERATION",
        JSON_SCRIPT,
        json_arguments,
    )

    if roi_temp_path is not None:
        roi_temp_path.unlink(missing_ok=True)

    # -----------------------------------------------------
    # STEP 6. Baseline 이력 누적
    # -----------------------------------------------------
    PIPELINE_CONTEXT["step_name"] = "BASELINE_HISTORY_UPDATE"
    history_digest_before = file_digest(history_json_path)
    baseline_mode = "UPDATE" if baseline_available else "INITIAL"
    run_step(
        6,
        "BASELINE HISTORY UPDATE",
        HISTORY_SCRIPT,
        [
            make_path_argument(result_paths["analysis_result"]),
            "--history-json",
            make_path_argument(history_json_path),
            "--interval-csv",
            make_path_argument(result_paths["interval_features"]),
            "--mode",
            baseline_mode,
        ],
    )
    history_changed = history_digest_before != file_digest(history_json_path)

    # -----------------------------------------------------
    # STEP 7. Baseline 생성 또는 갱신
    # 유효 날짜가 기준 일수 이상이면 최근 7일 기준으로 다시 계산한다.
    # -----------------------------------------------------
    baseline_created = False
    baseline_refreshed = False

    if history_changed and is_history_ready(history_json_path):
        PIPELINE_CONTEXT["step_name"] = "BASELINE_BUILD"
        baseline_step_name = (
            "BASELINE REFRESH"
            if baseline_available
            else "INITIAL BASELINE BUILD"
        )
        run_step(
            7,
            baseline_step_name,
            BASELINE_BUILD_SCRIPT,
            [
                make_path_argument(history_json_path),
                "--mode",
                baseline_mode,
                "--output-json",
                make_path_argument(baseline_json_path),
                "--output-csv",
                make_path_argument(baseline_csv_path),
            ],
        )

        validate_baseline_file_set(
            baseline_json_path,
            baseline_csv_path,
            inputs["baseline_identity"],
        )

        if baseline_available:
            baseline_refreshed = True
        else:
            baseline_created = True

    # -----------------------------------------------------
    # 완료 결과
    # -----------------------------------------------------
    total_time = time.time() - pipeline_start

    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    print(f"Current Video     : {current_video_path.name}")
    print(f"Registered Pet    : {pet_type}")
    print(f"Baseline CSV      : {baseline_csv_path.name}")
    print(
        "Baseline Status   : "
        + ("CREATED" if baseline_created else (
            "REFRESHED" if baseline_refreshed else (
                "READY" if baseline_available else "NOT_READY"
            )
        ))
    )

    print(
        f"Tracking Quality  : "
        f"{quality['tracking_quality']}"
    )

    print("Tracking          : COMPLETE")
    print("Feature Extraction: COMPLETE")
    print(f"Change Detection  : {change_step_status}")
    print("Result JSON       : COMPLETE")
    print("History Update    : COMPLETE")

    print(f"Total Time        : {total_time:.2f} sec")

    print()
    print("-" * 60)
    print("RESULT FILES")
    print("-" * 60)

    print(f"Tracking CSV       : {result_paths['tracking']}")

    print(
        f"Tracking Quality   : "
        f"{result_paths['quality']}"
    )

    print(
        f"Overall Features   : "
        f"{result_paths['features']}"
    )

    print(
        f"Interval Features  : "
        f"{result_paths['interval_features']}"
    )

    if baseline_available:
        print(
            f"Change Detail      : "
            f"{result_paths['change_detail']}"
        )

        print(
            f"Change Summary     : "
            f"{result_paths['change_summary']}"
        )

    else:
        print("Change Detail      : NOT_CREATED")
        print("Change Summary     : NOT_CREATED")

    print(f"Baseline History   : {history_json_path}")

    if baseline_csv_path.exists():
        print(f"Baseline CSV       : {baseline_csv_path}")
        print(f"Baseline JSON      : {baseline_json_path}")

    print(
        f"Integrated JSON    : "
        f"{result_paths['analysis_result']}"
    )


# =========================================================
# 11. 프로그램 시작
# =========================================================
if __name__ == "__main__":
    try:
        main()

    except AnalysisIdConflictError as error:
        print()
        print("=" * 60)
        print("ANALYSIS ID CONFLICT")
        print("=" * 60)
        print(f"Error: {error}")
        print("기존 분석 결과는 변경되지 않았습니다.")
        sys.exit(1)

    except BaselinePolicyError as error:
        print()
        print("=" * 60)
        print("BASELINE POLICY ERROR")
        print("=" * 60)
        print(f"Error Code : {error.code}")
        print(f"Message    : {error.message}")
        print("기존 Baseline과 history는 변경되지 않았습니다.")
        sys.exit(1)

    except Exception as error:
        failure_output = None

        if PIPELINE_CONTEXT:
            analysis_id = PIPELINE_CONTEXT.get("inputs", {}).get("analysis_id")
            if analysis_id:
                (ROI_TEMP_DIR / f"{analysis_id}_space_analysis.json").unlink(missing_ok=True)

        if PIPELINE_CONTEXT:
            try:
                error_code = classify_pipeline_error(
                    error,
                    PIPELINE_CONTEXT.get("step_name", "UNKNOWN"),
                )
                failure_output = save_failed_result(
                    PIPELINE_CONTEXT["inputs"],
                    PIPELINE_CONTEXT["started_at"],
                    error_code,
                    str(error),
                )
            except Exception as failure_error:
                print(f"Failure JSON Error: {failure_error}")

        print()
        print("=" * 60)
        print("PIPELINE FAILED")
        print("=" * 60)
        print(f"Error: {error}")

        if failure_output is not None:
            print(f"Failure JSON: {failure_output}")

        sys.exit(1)
