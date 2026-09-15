import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker


# =========================================================
# 1. 프로젝트 경로
# =========================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "outputs"
)

SCHEMA_PATH = (
    PROJECT_ROOT
    / "schemas"
    / "analysis_result.schema.json"
)

RESULT_DIR = (
    OUTPUT_DIR
    / "analysis_results"
)


# =========================================================
# 2. 피처 및 상태 매핑
# =========================================================
FEATURES = {
    "activity_level": [
        "activity_level",
    ],
    "stationary_ratio": [
        "stationary_ratio",
    ],
    "normalized_travel_distance": [
        "normalized_travel_distance",
        "travel_distance",
    ],
    "normalized_moving_speed": [
        "normalized_moving_speed",
        "moving_speed",
    ],
}

FEATURE_NAME_MAP = {
    "activity_level":
        "activity_level",

    "stationary_ratio":
        "stationary_ratio",

    "travel_distance":
        "normalized_travel_distance",

    "normalized_travel_distance":
        "normalized_travel_distance",

    "moving_speed":
        "normalized_moving_speed",

    "normalized_moving_speed":
        "normalized_moving_speed",
}

DIRECTION_MAP = {
    "increase": "INCREASE",
    "decrease": "DECREASE",
    "stable": "STABLE",
}

LEVEL_MAP = {
    "LOW": "NORMAL",
    "MODERATE": "SLIGHT",
    "HIGH": "STRONG",
    "VERY_HIGH": "STRONG",
}

# 기존 모델의 CHANGE 상태는
# 확정 JSON 명세의 STRONG_CHANGE로 통합한다.
STATUS_MAP = {
    "NORMAL": "NORMAL",
    "SLIGHT_CHANGE": "SLIGHT_CHANGE",
    "CHANGE": "STRONG_CHANGE",
    "STRONG_CHANGE": "STRONG_CHANGE",
}


# =========================================================
# 3. 공통 변환 함수
# =========================================================
def now_iso():
    return (
        datetime.now(timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def round_value(
    value,
    digits=6,
):
    """
    숫자를 최대 소수점 6자리로 반올림한다.
    NaN과 Infinity는 None으로 처리한다.
    """
    if value is None:
        return None

    try:
        value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(value):
        return None

    return round(
        value,
        digits,
    )


def to_int(
    value,
    default=0,
):
    try:
        if pd.isna(value):
            return default

        return int(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return default


def to_bool(value):
    if isinstance(value, bool):
        return value

    return (
        str(value)
        .strip()
        .lower()
        in {
            "true",
            "1",
            "yes",
        }
    )


def get_value(
    data,
    candidates,
    default=None,
):
    """
    후보 컬럼명 중 실제로 존재하는
    첫 번째 컬럼의 값을 반환한다.
    """
    for name in candidates:
        if name not in data:
            continue

        value = data[name]

        if isinstance(
            value,
            pd.Series,
        ):
            value = value.iloc[0]

        if pd.isna(value):
            continue

        return value

    return default


def resolve_project_path(path_value):
    """
    상대 경로는 프로젝트 루트 기준으로,
    절대 경로는 그대로 처리한다.
    """
    path = Path(path_value)

    if not path.is_absolute():
        path = (
            PROJECT_ROOT
            / path
        )

    return path.resolve()


# =========================================================
# 4. CSV 파일 확인 및 읽기
# =========================================================
def find_csv(
    video_stem,
    suffix,
):
    path = (
        OUTPUT_DIR
        / f"{video_stem}{suffix}"
    )

    if not path.exists():
        raise FileNotFoundError(
            "필요한 결과 CSV를 찾을 수 없습니다.\n"
            f"{path}"
        )

    return path


def read_single_row_csv(path):
    dataframe = pd.read_csv(path)

    if dataframe.empty:
        raise ValueError(
            f"CSV가 비어 있습니다: {path.name}"
        )

    return dataframe.iloc[0]


# =========================================================
# 5. 영상 정보 생성
# =========================================================
def read_video_info(video_path):
    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():
        raise ValueError(
            f"영상 파일을 열 수 없습니다: {video_path}"
        )

    fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    capture.release()

    if (
        fps <= 0
        or total_frames <= 0
        or width <= 0
        or height <= 0
    ):
        raise ValueError(
            "영상 기본 정보를 정상적으로 읽지 못했습니다."
        )

    duration_sec = (
        total_frames
        / fps
    )

    return {
        "file_name":
            video_path.name,

        "duration_sec":
            round_value(duration_sec),

        "fps":
            round_value(fps),

        "width":
            width,

        "height":
            height,

        "total_frames":
            total_frames,
    }


# =========================================================
# 6. Tracking 품질 정보 생성
# =========================================================
def build_tracking_quality(
    tracking_row,
    total_frames,
):
    raw_detected = to_int(
        get_value(
            tracking_row,
            [
                "raw_detected_frames",
                "raw_detected",
                "detected_frames",
            ],
        )
    )

    interpolated = to_int(
        get_value(
            tracking_row,
            [
                "interpolated_frames",
                "interpolated",
            ],
        )
    )

    jump_filtered = to_int(
        get_value(
            tracking_row,
            [
                "jump_filtered_frames",
                "jump_filtered",
            ],
        )
    )

    missing_frames_value = get_value(
        tracking_row,
        [
            "missing_frames",
            "remaining_missing",
            "missing_count",
        ],
    )

    if missing_frames_value is None:
        missing_ratio = round_value(
            get_value(
                tracking_row,
                [
                    "missing_ratio",
                ],
                0,
            )
        )

        missing_frames = round(
            total_frames
            * (missing_ratio or 0)
        )

    else:
        missing_frames = to_int(
            missing_frames_value
        )

    valid_frames = get_value(
        tracking_row,
        [
            "valid_tracking_frames",
            "valid_frames",
            "usable_frames",
        ],
    )

    if valid_frames is None:
        # Tracking 결과에서 실제로 확보한 좌표 수를 우선 사용한다.
        # 영상 메타데이터의 CAP_PROP_FRAME_COUNT는 디코딩된 실제
        # 프레임 수와 다를 수 있으므로 total_frames로 대체하지 않는다.
        detected_and_interpolated = (
            raw_detected
            + interpolated
        )

        if detected_and_interpolated > 0:
            valid_frames = detected_and_interpolated

        else:
            valid_frames = (
                total_frames
                - missing_frames
            )

    valid_frames = to_int(
        valid_frames
    )

    valid_frames = max(
        0,
        min(
            valid_frames,
            total_frames,
        ),
    )

    missing_frames = max(
        0,
        min(
            missing_frames,
            total_frames,
        ),
    )

    processed_frames = (
        valid_frames
        + missing_frames
    )

    tracking_success_rate = round_value(
        valid_frames / processed_frames
        if processed_frames > 0
        else 0
    )

    if tracking_success_rate >= 0.90:
        quality_status = "GOOD"

    elif tracking_success_rate >= 0.70:
        quality_status = "WARNING"

    else:
        quality_status = "INSUFFICIENT"

    return {
        "raw_detected_frames":
            raw_detected,

        "interpolated_frames":
            interpolated,

        "jump_filtered_frames":
            jump_filtered,

        "valid_tracking_frames":
            valid_frames,

        "missing_frames":
            missing_frames,

        "tracking_success_rate":
            tracking_success_rate,

        "quality_status":
            quality_status,
    }


# =========================================================
# 7. 전체 피처 생성
# =========================================================
def map_features(row):
    result = {}

    for (
        json_name,
        candidates,
    ) in FEATURES.items():
        value = round_value(
            get_value(
                row,
                candidates,
            )
        )

        if value is None:
            raise ValueError(
                "피처 값을 찾을 수 없습니다.\n"
                f"필요한 피처: {json_name}\n"
                f"확인한 후보 컬럼: {candidates}\n"
                f"실제 CSV 컬럼: {list(row.index)}"
            )

        result[json_name] = value

    return result


# =========================================================
# 8. 구간별 피처 생성
# =========================================================
def build_interval_features(
    interval_dataframe,
):
    result = []

    for (
        _,
        row,
    ) in interval_dataframe.iterrows():
        start_sec = round_value(
            get_value(
                row,
                [
                    "start_sec",
                    "interval_start_sec",
                    "start_time",
                ],
            )
        )

        end_sec = round_value(
            get_value(
                row,
                [
                    "end_sec",
                    "interval_end_sec",
                    "end_time",
                ],
            )
        )

        if (
            start_sec is None
            or end_sec is None
        ):
            raise ValueError(
                "구간 시작·종료 시간을 찾을 수 없습니다.\n"
                f"실제 CSV 컬럼: {list(row.index)}"
            )

        valid_frames = to_int(
            get_value(
                row,
                [
                    "valid_tracking_frames",
                    "valid_frames",
                    "usable_frames",
                    "frames_used",
                    "measurements",
                    "measurement_count",
                ],
            )
        )

        interval_result = {
            "start_sec":
                start_sec,

            "end_sec":
                end_sec,

            "valid_tracking_frames":
                valid_frames,

            **map_features(row),
        }

        result.append(
            interval_result
        )

    return result


# =========================================================
# 9. 변화 감지 결과 생성
# =========================================================
def build_change_detection(
    detail_csv,
    summary_csv,
    quality_status,
):
    if quality_status == "INSUFFICIENT":
        return [], {
            "baseline_status":
                "NOT_READY",

            "change_score":
                None,

            "change_status":
                "NOT_EVALUATED",

            "evaluated_feature_count":
                0,

            "threshold_exceeded_count":
                0,

            "contributing_factors":
                [],
        }

    if (
        not detail_csv.exists()
        or not summary_csv.exists()
    ):
        return [], {
            "baseline_status":
                "NOT_READY",

            "change_score":
                None,

            "change_status":
                "NOT_EVALUATED",

            "evaluated_feature_count":
                0,

            "threshold_exceeded_count":
                0,

            "contributing_factors":
                [],
        }

    detail_dataframe = pd.read_csv(
        detail_csv
    )

    summary_dataframe = pd.read_csv(
        summary_csv
    )

    if (
        detail_dataframe.empty
        or summary_dataframe.empty
    ):
        return [], {
            "baseline_status":
                "NOT_READY",

            "change_score":
                None,

            "change_status":
                "NOT_EVALUATED",

            "evaluated_feature_count":
                0,

            "threshold_exceeded_count":
                0,

            "contributing_factors":
                [],
        }

    baseline_comparison = []
    contributing_factors = []

    for (
        _,
        row,
    ) in detail_dataframe.iterrows():
        raw_feature = str(
            get_value(
                row,
                ["feature"],
                "",
            )
        ).strip()

        feature = FEATURE_NAME_MAP.get(
            raw_feature
        )

        if feature is None:
            continue

        current_value = round_value(
            get_value(
                row,
                ["current_value"],
            )
        )

        baseline_mean = round_value(
            get_value(
                row,
                ["baseline_mean"],
            )
        )

        baseline_std = round_value(
            get_value(
                row,
                ["baseline_std"],
            )
        )

        # 표준편차가 0이면 해당 피처 비교 제외
        if (
            baseline_std is None
            or baseline_std <= 0
        ):
            baseline_comparison.append(
                {
                    "feature":
                        feature,

                    "comparison_status":
                        "NOT_EVALUATED",

                    "current_value":
                        current_value,

                    "baseline_mean":
                        baseline_mean,

                    "baseline_std":
                        baseline_std or 0.0,

                    "z_score":
                        None,

                    "direction":
                        None,

                    "level":
                        None,

                    "threshold_exceeded":
                        None,
                }
            )

            continue

        direction_raw = str(
            get_value(
                row,
                ["direction"],
                "stable",
            )
        ).strip().lower()

        level_raw = str(
            get_value(
                row,
                ["change_level"],
                "LOW",
            )
        ).strip().upper()

        comparison = {
            "feature":
                feature,

            "comparison_status":
                "EVALUATED",

            "current_value":
                current_value,

            "baseline_mean":
                baseline_mean,

            "baseline_std":
                baseline_std,

            "z_score":
                round_value(
                    get_value(
                        row,
                        ["z_score"],
                    )
                ),

            "direction":
                DIRECTION_MAP.get(
                    direction_raw,
                    "STABLE",
                ),

            "level":
                LEVEL_MAP.get(
                    level_raw,
                    "NORMAL",
                ),

            "threshold_exceeded":
                to_bool(
                    get_value(
                        row,
                        ["is_changed"],
                        False,
                    )
                ),
        }

        baseline_comparison.append(
            comparison
        )

        if to_bool(
            get_value(
                row,
                ["is_factor"],
                False,
            )
        ):
            factor_level = comparison["level"]

            # 명세에서 주요 변화 요인의 단계는
            # SLIGHT 또는 STRONG만 허용한다.
            if factor_level == "NORMAL":
                factor_level = "SLIGHT"

            contributing_factors.append(
                {
                    "feature":
                        feature,

                    "direction":
                        comparison["direction"],

                    "z_score":
                        comparison["z_score"],

                    "level":
                        factor_level,
                }
            )

    contributing_factors.sort(
        key=lambda item: abs(
            item["z_score"]
        ),
        reverse=True,
    )

    summary = summary_dataframe.iloc[0]

    raw_status = str(
        get_value(
            summary,
            ["status"],
            "NORMAL",
        )
    ).strip().upper()

    change_status = STATUS_MAP.get(
        raw_status,
        "NOT_EVALUATED",
    )

    change_score = round_value(
        get_value(
            summary,
            ["change_score"],
        )
    )

    evaluated_feature_count = sum(
        item["comparison_status"]
        == "EVALUATED"
        for item in baseline_comparison
    )

    threshold_exceeded_count = sum(
        item["threshold_exceeded"] is True
        for item in baseline_comparison
        if (
            item["comparison_status"]
            == "EVALUATED"
        )
    )

    return baseline_comparison, {
        "baseline_status":
            "READY",

        "change_score":
            change_score,

        "change_status":
            change_status,

        "evaluated_feature_count":
            evaluated_feature_count,

        "threshold_exceeded_count":
            threshold_exceeded_count,

        "contributing_factors":
            contributing_factors,
    }


# =========================================================
# 10. JSON Schema 검증
# =========================================================
def validate_result(result):
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            "Schema 파일을 찾을 수 없습니다.\n"
            f"{SCHEMA_PATH}"
        )

    with open(
        SCHEMA_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        schema = json.load(file)

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )

    errors = sorted(
        validator.iter_errors(result),
        key=lambda error: list(
            error.absolute_path
        ),
    )

    if errors:
        messages = []

        for error in errors:
            location = ".".join(
                map(
                    str,
                    error.absolute_path,
                )
            )

            if not location:
                location = "root"

            messages.append(
                f"- {location}: {error.message}"
            )

        raise ValueError(
            "생성된 JSON이 Schema 검증에 실패했습니다.\n"
            + "\n".join(messages)
        )


# =========================================================
# 11. 명령행 입력
# =========================================================
def get_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "PET 분석 결과 CSV를 "
            "최종 통합 JSON으로 생성합니다."
        )
    )

    parser.add_argument(
        "--video",
        required=True,
        help="분석 영상 경로",
    )

    parser.add_argument(
        "--species",
        required=True,
        choices=[
            "DOG",
            "CAT",
        ],
        help="등록된 반려동물 종",
    )

    parser.add_argument(
        "--analysis-id",
        required=True,
        help="분석 ID",
    )

    parser.add_argument(
        "--pet-id",
        required=True,
        help="반려동물 ID",
    )

    parser.add_argument(
        "--video-id",
        required=True,
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
        help="영상 촬영 시각",
    )

    parser.add_argument(
        "--recorded-at-source",
        default="REQUEST_TIME",
        choices=[
            "CAMERA",
            "FILE_METADATA",
            "REQUEST_TIME",
        ],
        help="촬영 시각 출처",
    )

    parser.add_argument(
        "--time-slot",
        default="09:00-10:00",
        help="베이스라인 비교 시간대",
    )

    parser.add_argument(
        "--started-at",
        default=None,
        help="전체 파이프라인 분석 시작 시각",
    )

    # run_pipeline.py에서 실제 생성된
    # 변화 감지 결과 경로를 전달받는다.
    parser.add_argument(
        "--change-detail-csv",
        default=None,
        help="변화 감지 상세 CSV 경로",
    )

    parser.add_argument(
        "--change-summary-csv",
        default=None,
        help="변화 감지 요약 CSV 경로",
    )

    return parser.parse_args()


# =========================================================
# 12. 메인 실행
# =========================================================
def main():
    args = get_arguments()

    video_path = resolve_project_path(
        args.video
    )

    if not video_path.exists():
        raise FileNotFoundError(
            "원본 영상 파일을 찾을 수 없습니다.\n"
            f"{video_path}"
        )

    video_stem = video_path.stem

    # run_pipeline.py에서 전달받은 전체 분석 시작 시각을 사용한다.
    # 단독 실행 시에는 현재 시각을 사용한다.
    started_at = args.started_at or now_iso()

    tracking_csv = find_csv(
        video_stem,
        "_tracking_quality.csv",
    )

    overall_csv = find_csv(
        video_stem,
        "_features.csv",
    )

    interval_csv = find_csv(
        video_stem,
        "_features_by_interval.csv",
    )

    # 전달받은 변화 감지 파일이 있으면 해당 경로를 사용한다.
    if args.change_detail_csv:
        change_detail_csv = resolve_project_path(
            args.change_detail_csv
        )

    else:
        change_detail_csv = (
            OUTPUT_DIR
            / f"{video_stem}_change_detection.csv"
        )

    if args.change_summary_csv:
        change_summary_csv = resolve_project_path(
            args.change_summary_csv
        )

    else:
        change_summary_csv = (
            OUTPUT_DIR
            / f"{video_stem}_change_summary.csv"
        )

    video_info = read_video_info(
        video_path
    )

    tracking_row = read_single_row_csv(
        tracking_csv
    )

    overall_row = read_single_row_csv(
        overall_csv
    )

    interval_dataframe = pd.read_csv(
        interval_csv
    )

    tracking_quality = build_tracking_quality(
        tracking_row,
        video_info["total_frames"],
    )

    features_overall = map_features(
        overall_row
    )

    features_by_interval = build_interval_features(
        interval_dataframe
    )

    (
        baseline_comparison,
        change_detection,
    ) = build_change_detection(
        change_detail_csv,
        change_summary_csv,
        tracking_quality["quality_status"],
    )

    warnings = []

    if (
        tracking_quality["quality_status"]
        == "WARNING"
    ):
        warnings.append(
            {
                "code":
                    "LOW_TRACKING_QUALITY",

                "message":
                    "일부 프레임의 추적 품질이 낮습니다.",
            }
        )

    if (
        1.0
        <= video_info["duration_sec"]
        < 5.0
    ):
        warnings.append(
            {
                "code":
                    "SHORT_VIDEO_WARNING",

                "message":
                    "영상 길이가 권장 분석 길이보다 짧습니다.",
            }
        )

    if warnings:
        analysis_status = (
            "COMPLETED_WITH_WARNING"
        )

    else:
        analysis_status = "COMPLETED"

    result = {
        "schema_version":
            "1.1",

        "analysis_id":
            args.analysis_id,

        "pet_id":
            args.pet_id,

        "video_id":
            args.video_id,

        "camera_id":
            args.camera_id,

        "species":
            args.species,

        "analysis_status":
            analysis_status,

        "recorded_at":
            args.recorded_at or now_iso(),

        "recorded_at_source":
            args.recorded_at_source,

        "aggregation_sec":
            5.0,

        "time_slot":
            args.time_slot,

        "started_at":
            started_at,

        "completed_at":
            now_iso(),

        "video_info":
            video_info,

        "tracking_quality":
            tracking_quality,

        "features_overall":
            features_overall,

        "features_by_interval":
            features_by_interval,

        "baseline_comparison":
            baseline_comparison,

        "change_detection":
            change_detection,

        "space_analysis":
            None,

        "model_info": {
            "pipeline_version":
                "pet-behavior-v1.1",

            "feature_version":
                "pet-features-v2.0",

            "detector":
                "YOLO11s",

            "movement_window_sec":
                1.0,

            "movement_threshold":
                0.04,

            "aggregation_sec":
                5.0,

            "std_zero_policy":
                "EXCLUDE_FEATURE",
        },

        "warnings":
            warnings,

        "error":
            None,
    }

    validate_result(
        result
    )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULT_DIR
        / f"{args.analysis_id}_result.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 55)
    print("PET ANALYSIS RESULT JSON CREATED")
    print("=" * 55)

    print(
        f"Analysis ID : "
        f"{args.analysis_id}"
    )

    print(
        f"Species     : "
        f"{args.species}"
    )

    print(
        f"Status      : "
        f"{analysis_status}"
    )

    print(
        f"Change      : "
        f"{change_detection['change_status']}"
    )

    print(
        f"Score       : "
        f"{change_detection['change_score']}"
    )

    print(
        f"Output      : "
        f"{output_path}"
    )

    print("=" * 55)


# =========================================================
# 13. 프로그램 시작
# =========================================================
if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print()
        print("=" * 55)
        print("JSON GENERATION FAILED")
        print("=" * 55)
        print(f"Error: {error}")

        sys.exit(1)
