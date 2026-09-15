import csv
import math
import sys
from pathlib import Path
from statistics import mean


# =========================================================
# 1. 프로젝트 경로
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
)


# =========================================================
# 2. 현재 분석 영상 결정
# =========================================================
# 기본 사용:
#
# python src/detect_change.py \
#     data/videos/cat_tracking_test3.mov
#
# 실제 7일 이력으로 생성한 Baseline CSV와 비교:
#
# python src/detect_change.py \
#     data/videos/current_video.mp4 \
#     data/outputs/baselines/PET-0001_08-00-09-00_baseline_features.csv
# =========================================================
if len(sys.argv) >= 2:
    current_input_path = Path(
        sys.argv[1]
    )

    if current_input_path.is_absolute():
        CURRENT_VIDEO_PATH = (
            current_input_path
        )
    else:
        CURRENT_VIDEO_PATH = (
            BASE_DIR
            / current_input_path
        )

else:
    CURRENT_VIDEO_PATH = (
        BASE_DIR
        / "data"
        / "videos"
        / "pet_tracking_test.mp4"
    )

CURRENT_VIDEO_PATH = (
    CURRENT_VIDEO_PATH.resolve()
)


# =========================================================
# 3. Baseline CSV 결정
# =========================================================
if len(sys.argv) >= 3:
    baseline_input_path = Path(
        sys.argv[2]
    )

    if baseline_input_path.is_absolute():
        BASELINE_PATH = (
            baseline_input_path
        )
    else:
        BASELINE_PATH = (
            BASE_DIR
            / baseline_input_path
        )

else:
    raise ValueError(
        "Baseline CSV 경로를 입력해주세요.\n"
        "예: python src/detect_change.py "
        "data/videos/current_video.mp4 "
        "data/outputs/baselines/"
        "PET-0001_08-00-09-00_baseline_features.csv"
    )

BASELINE_PATH = (
    BASELINE_PATH.resolve()
)


# =========================================================
# 4. 영상별 입출력 경로
# =========================================================
CURRENT_VIDEO_NAME = (
    CURRENT_VIDEO_PATH.stem
)

CURRENT_INTERVAL_FEATURE_PATH = (
    OUTPUT_DIR
    / f"{CURRENT_VIDEO_NAME}_features_by_interval.csv"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{CURRENT_VIDEO_NAME}_change_detection.csv"
)

SUMMARY_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{CURRENT_VIDEO_NAME}_change_summary.csv"
)


# =========================================================
# 5. 분석 설정
# =========================================================
FEATURE_NAMES = [
    "activity_level",
    "stationary_ratio",
    "travel_distance",
    "moving_speed"
]


# 피처 집계 단위
AGGREGATION_SECONDS = 5.0


# 완전한 구간으로 인정할 최소 분석 시간
MIN_COMPLETE_INTERVAL_RATIO = 0.90

MIN_COMPLETE_INTERVAL_SECONDS = (
    AGGREGATION_SECONDS
    * MIN_COMPLETE_INTERVAL_RATIO
)


# 개별 피처가 명확하게 변했다고 판단하는 기준
CHANGE_Z_THRESHOLD = 2.0


# 주요 변화 요인 후보 기준
FACTOR_Z_THRESHOLD = 1.0


# 변화 점수 계산 시 Z-score 최대 반영값
MAX_Z_FOR_SCORE = 4.0


# =========================================================
# 6. 입력 파일 확인
# =========================================================
if not CURRENT_VIDEO_PATH.exists():
    raise FileNotFoundError(
        "현재 분석 영상을 찾을 수 없습니다.\n"
        f"{CURRENT_VIDEO_PATH}"
    )

if not CURRENT_INTERVAL_FEATURE_PATH.exists():
    raise FileNotFoundError(
        "현재 영상의 구간별 Feature CSV를 "
        "찾을 수 없습니다.\n"
        f"{CURRENT_INTERVAL_FEATURE_PATH}\n\n"
        "먼저 extract_features.py를 "
        "실행해주세요."
    )

if not BASELINE_PATH.exists():
    raise FileNotFoundError(
        "Baseline CSV를 찾을 수 없습니다.\n"
        f"{BASELINE_PATH}\n\n"
        "먼저 build_baseline_from_history.py를 실행해주세요."
    )


# =========================================================
# 7. 구간별 Feature CSV 읽기
# =========================================================
def load_interval_features(
    interval_feature_path
):
    interval_records = []

    with open(
        interval_feature_path,
        "r",
        encoding="utf-8-sig"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        required_columns = {
            "interval_start_sec",
            "interval_end_sec",
            "activity_level",
            "stationary_ratio",
            "travel_distance",
            "moving_speed"
        }

        if reader.fieldnames is None:
            raise ValueError(
                "구간별 Feature CSV의 "
                "헤더를 읽을 수 없습니다."
            )

        missing_columns = (
            required_columns
            - set(reader.fieldnames)
        )

        if len(missing_columns) > 0:
            raise ValueError(
                "구간별 Feature CSV에 필요한 "
                "컬럼이 없습니다.\n"
                f"누락 컬럼: "
                f"{sorted(missing_columns)}"
            )

        has_analyzed_duration = (
            "analyzed_duration"
            in reader.fieldnames
        )

        for row in reader:
            interval_start = float(
                row["interval_start_sec"]
            )

            interval_end = float(
                row["interval_end_sec"]
            )

            if has_analyzed_duration:
                analyzed_duration = float(
                    row["analyzed_duration"]
                )
            else:
                analyzed_duration = (
                    interval_end
                    - interval_start
                )

            record = {
                "interval_start_sec":
                    interval_start,

                "interval_end_sec":
                    interval_end,

                "analyzed_duration":
                    analyzed_duration
            }

            for feature_name in FEATURE_NAMES:
                record[feature_name] = float(
                    row[feature_name]
                )

            interval_records.append(
                record
            )

    if len(interval_records) == 0:
        raise ValueError(
            "구간별 Feature CSV에 "
            "데이터가 없습니다."
        )

    return interval_records


# =========================================================
# 8. 완전한 구간만 선택
# =========================================================
def select_complete_intervals(
    interval_records
):
    complete_intervals = [
        record
        for record in interval_records
        if (
            record["analyzed_duration"]
            >= MIN_COMPLETE_INTERVAL_SECONDS
        )
    ]

    if len(complete_intervals) == 0:
        raise ValueError(
            "변화 감지에 사용할 수 있는 "
            "완전한 5초 구간이 없습니다.\n"
            f"필요 분석 시간: "
            f"{MIN_COMPLETE_INTERVAL_SECONDS:.2f}초 이상"
        )

    return complete_intervals


# =========================================================
# 9. 현재 영상의 대표 Feature 계산
# =========================================================
def calculate_current_features(
    complete_intervals
):
    current_features = {}

    for feature_name in FEATURE_NAMES:
        feature_values = [
            record[feature_name]
            for record in complete_intervals
        ]

        current_features[feature_name] = mean(
            feature_values
        )

    return current_features


# =========================================================
# 10. Baseline 읽기
# =========================================================
def load_baseline(
    baseline_path
):
    baseline = {}

    with open(
        baseline_path,
        "r",
        encoding="utf-8-sig"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        required_columns = {
            "feature",
            "mean",
            "std"
        }

        if reader.fieldnames is None:
            raise ValueError(
                "Baseline CSV의 헤더를 "
                "읽을 수 없습니다."
            )

        missing_columns = (
            required_columns
            - set(reader.fieldnames)
        )

        if len(missing_columns) > 0:
            raise ValueError(
                "Baseline CSV에 필요한 "
                "컬럼이 없습니다.\n"
                f"누락 컬럼: "
                f"{sorted(missing_columns)}"
            )

        for row in reader:
            feature_name = (
                row["feature"]
            )

            baseline[feature_name] = {
                "mean":
                    float(
                        row["mean"]
                    ),

                "std":
                    float(
                        row["std"]
                    )
            }

    for feature_name in FEATURE_NAMES:
        if feature_name not in baseline:
            raise ValueError(
                f"{feature_name} Baseline이 없습니다."
            )

    return baseline


# =========================================================
# 11. Z-score 계산
# =========================================================
def calculate_z_score(
    current,
    baseline_mean,
    baseline_std
):
    if baseline_std <= 1e-8:
        return None

    return (
        current
        - baseline_mean
    ) / baseline_std


# =========================================================
# 12. 변화 방향 계산
# =========================================================
def get_direction(
    current,
    baseline_mean
):
    if math.isclose(
        current,
        baseline_mean,
        rel_tol=1e-9,
        abs_tol=1e-9
    ):
        return "same"

    if current > baseline_mean:
        return "increase"

    return "decrease"


# =========================================================
# 13. 피처별 변화 단계
# =========================================================
def get_change_level(
    absolute_z_score
):
    if absolute_z_score < 1.0:
        return "LOW"

    if absolute_z_score < 2.0:
        return "MODERATE"

    if absolute_z_score < 3.0:
        return "HIGH"

    return "VERY_HIGH"


# =========================================================
# 14. 피처별 변화 분석
# =========================================================
def analyze_features(
    current_features,
    baseline
):
    results = []

    for feature_name in FEATURE_NAMES:
        current_value = (
            current_features[
                feature_name
            ]
        )

        baseline_mean = (
            baseline[
                feature_name
            ]["mean"]
        )

        baseline_std = (
            baseline[
                feature_name
            ]["std"]
        )

        z_score = calculate_z_score(
            current_value,
            baseline_mean,
            baseline_std
        )

        if z_score is None:
            absolute_z_score = None
            direction = None
            change_level = None
            is_changed = False
            is_factor = False

        else:
            absolute_z_score = abs(
                z_score
            )

            direction = get_direction(
                current_value,
                baseline_mean
            )

            change_level = get_change_level(
                absolute_z_score
            )

            is_changed = (
                absolute_z_score
                >= CHANGE_Z_THRESHOLD
            )

            is_factor = (
                absolute_z_score
                >= FACTOR_Z_THRESHOLD
            )

        results.append({
            "feature":
                feature_name,

            "current":
                current_value,

            "baseline_mean":
                baseline_mean,

            "baseline_std":
                baseline_std,

            "z_score":
                z_score,

            "abs_z":
                absolute_z_score,

            "direction":
                direction,

            "change_level":
                change_level,

            "is_changed":
                is_changed,

            "is_factor":
                is_factor
        })

    return results


# =========================================================
# 15. 종합 변화 점수 계산
# =========================================================
def calculate_change_score(
    feature_results
):
    normalized_scores = []

    for result in feature_results:
        if result["abs_z"] is None:
            continue

        capped_z_score = min(
            result["abs_z"],
            MAX_Z_FOR_SCORE
        )

        normalized_score = (
            capped_z_score
            / MAX_Z_FOR_SCORE
        )

        normalized_scores.append(
            normalized_score
        )

    if len(normalized_scores) == 0:
        return None

    average_score = (
        sum(normalized_scores)
        / len(normalized_scores)
    )

    return (
        average_score
        * 100
    )


# =========================================================
# 16. 주요 변화 요인 추출
# =========================================================
def get_major_factors(
    feature_results,
    top_n=3
):
    factor_candidates = [
        result
        for result in feature_results
        if result["is_factor"]
    ]

    factor_candidates.sort(
        key=lambda item:
            item["abs_z"],
        reverse=True
    )

    return factor_candidates[:top_n]


# =========================================================
# 17. 종합 변화 상태 판정
# =========================================================
def get_overall_status(
    change_score
):
    if change_score is None:
        return "NOT_EVALUATED"

    if change_score < 25:
        return "NORMAL"

    if change_score < 50:
        return "SLIGHT_CHANGE"

    if change_score < 75:
        return "CHANGE"

    return "STRONG_CHANGE"


# =========================================================
# 18. 현재 Feature 계산 및 변화 분석
# =========================================================
interval_records = load_interval_features(
    CURRENT_INTERVAL_FEATURE_PATH
)

complete_intervals = select_complete_intervals(
    interval_records
)

current_features = (
    calculate_current_features(
        complete_intervals
    )
)

baseline = load_baseline(
    BASELINE_PATH
)

feature_results = analyze_features(
    current_features,
    baseline
)

change_score = calculate_change_score(
    feature_results
)

overall_status = get_overall_status(
    change_score
)

major_factors = get_major_factors(
    feature_results
)

changed_feature_count = sum(
    1
    for result in feature_results
    if result["is_changed"]
)

factor_feature_count = sum(
    1
    for result in feature_results
    if result["is_factor"]
)


# =========================================================
# 19. 결과 폴더 생성
# =========================================================
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# 20. 상세 변화 감지 CSV 저장
# =========================================================
with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:
    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "feature",
        "current_value",
        "baseline_mean",
        "baseline_std",
        "z_score",
        "direction",
        "change_level",
        "is_changed",
        "is_factor"
    ])

    for result in feature_results:
        writer.writerow([
            result["feature"],

            round(
                result["current"],
                6
            ),

            round(
                result["baseline_mean"],
                6
            ),

            round(
                result["baseline_std"],
                6
            ),

            (
                round(result["z_score"], 6)
                if result["z_score"] is not None
                else ""
            ),

            result["direction"] or "",
            result["change_level"] or "",
            result["is_changed"],
            result["is_factor"]
        ])


# =========================================================
# 21. 변화 감지 요약 CSV 저장
# =========================================================
with open(
    SUMMARY_OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:
    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "current_video",
        "baseline_video",
        "complete_interval_count",
        "change_score",
        "status",
        "changed_feature_count",
        "factor_feature_count",
        "major_factor_1",
        "major_factor_2",
        "major_factor_3"
    ])

    major_factor_names = []

    for factor in major_factors:
        major_factor_names.append(
            (
                f"{factor['feature']}"
                f":{factor['direction']}"
                f":z={factor['z_score']:.3f}"
            )
        )

    while len(major_factor_names) < 3:
        major_factor_names.append(
            ""
        )

    writer.writerow([
        CURRENT_VIDEO_PATH.name,
        BASELINE_PATH.name,
        len(complete_intervals),

        (
            round(change_score, 2)
            if change_score is not None
            else ""
        ),

        overall_status,
        changed_feature_count,
        factor_feature_count,
        major_factor_names[0],
        major_factor_names[1],
        major_factor_names[2]
    ])


# =========================================================
# 22. 터미널 출력
# =========================================================
print()
print("=" * 55)
print("PET CHANGE DETECTION")
print("=" * 55)

print(
    f"Current Video      : "
    f"{CURRENT_VIDEO_PATH.name}"
)

print(
    f"Baseline CSV       : "
    f"{BASELINE_PATH.name}"
)

print(
    f"Current Feature CSV: "
    f"{CURRENT_INTERVAL_FEATURE_PATH.name}"
)

print(
    f"Complete Intervals : "
    f"{len(complete_intervals)}"
)

print()
print("-" * 55)
print("CURRENT REPRESENTATIVE FEATURES")
print("-" * 55)

for feature_name in FEATURE_NAMES:
    print(
        f"{feature_name:<18}: "
        f"{current_features[feature_name]:.6f}"
    )

print()
print("-" * 55)
print("FEATURE CHANGE DETAILS")
print("-" * 55)

for result in feature_results:
    print(
        result["feature"]
    )

    print(
        f"  current   : "
        f"{result['current']:.6f}"
    )

    print(
        f"  baseline  : "
        f"{result['baseline_mean']:.6f}"
        f" ± "
        f"{result['baseline_std']:.6f}"
    )

    print(
        "  z-score   : "
        + (
            f"{result['z_score']:.3f}"
            if result["z_score"] is not None
            else "NOT_EVALUATED"
        )
    )

    print(
        f"  direction : "
        f"{result['direction'] or 'NOT_EVALUATED'}"
    )

    print(
        f"  level     : "
        f"{result['change_level'] or 'NOT_EVALUATED'}"
    )

    print(
        f"  changed   : "
        f"{result['is_changed']}"
    )

    print(
        f"  factor    : "
        f"{result['is_factor']}"
    )

    print()

print("-" * 55)
print("OVERALL CHANGE")
print("-" * 55)

print(
    f"Change Score     : "
    + (
        f"{change_score:.2f} / 100"
        if change_score is not None
        else "NOT_EVALUATED"
    )
)

print(
    f"Status           : "
    f"{overall_status}"
)

print(
    f"Changed Features : "
    f"{changed_feature_count}"
)

print(
    f"Factor Features  : "
    f"{factor_feature_count}"
)

print()
print("Major Factors:")

if len(major_factors) == 0:
    print(
        "  None"
    )

else:
    for rank, factor in enumerate(
        major_factors,
        start=1
    ):
        print(
            f"  {rank}. "
            f"{factor['feature']} "
            f"({factor['direction']}) "
            f"| z="
            f"{factor['z_score']:.3f}"
        )

print()
print("=" * 55)
print("CHANGE DETECTION COMPLETE")
print("=" * 55)

print(
    f"Detail CSV : "
    f"{OUTPUT_PATH}"
)

print(
    f"Summary CSV: "
    f"{SUMMARY_OUTPUT_PATH}"
)
