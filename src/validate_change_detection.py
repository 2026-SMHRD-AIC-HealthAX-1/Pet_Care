import csv
import math
import sys
from pathlib import Path


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
# 2. 검증 대상 기준 영상
# =========================================================
# 강아지:
#
# python src/validate_change_detection.py \
#     data/videos/pet_tracking_test.mp4
#
# 고양이:
#
# python src/validate_change_detection.py \
#     data/videos/cat_tracking_test3.mov
# =========================================================
if len(sys.argv) >= 2:
    input_path = Path(
        sys.argv[1]
    )

    if input_path.is_absolute():
        VIDEO_PATH = input_path
    else:
        VIDEO_PATH = (
            BASE_DIR
            / input_path
        )

else:
    VIDEO_PATH = (
        BASE_DIR
        / "data"
        / "videos"
        / "pet_tracking_test.mp4"
    )

VIDEO_PATH = VIDEO_PATH.resolve()

VIDEO_NAME = VIDEO_PATH.stem


# =========================================================
# 3. 입출력 파일 경로
# =========================================================
BASELINE_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_baseline_features.csv"
)

DETAIL_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_change_validation_details.csv"
)

SUMMARY_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_change_validation_summary.csv"
)


# =========================================================
# 4. 변화 감지 설정
# =========================================================
FEATURE_NAMES = [
    "activity_level",
    "stationary_ratio",
    "travel_distance",
    "moving_speed"
]


# 명확하게 변한 피처 기준
CHANGE_Z_THRESHOLD = 2.0


# 주요 변화 요인 후보 기준
FACTOR_Z_THRESHOLD = 1.0


# 변화 점수에 반영할 최대 Z-score
MAX_Z_FOR_SCORE = 4.0


# =========================================================
# 5. 검증 시나리오
# =========================================================
# 각 값은 해당 피처에 적용할 목표 Z-score이다.
#
# stationary_ratio는 감소 방향,
# 나머지 피처는 증가 방향을 중심으로 구성한다.
# =========================================================
VALIDATION_SCENARIOS = {
    "NORMAL": {
        "activity_level": 0.20,
        "stationary_ratio": -0.30,
        "travel_distance": 0.10,
        "moving_speed": 0.25
    },

    "SLIGHT": {
        "activity_level": 1.40,
        "stationary_ratio": -1.60,
        "travel_distance": 1.30,
        "moving_speed": 1.50
    },

    "STRONG": {
        "activity_level": 3.50,
        "stationary_ratio": -3.80,
        "travel_distance": 3.20,
        "moving_speed": 3.40
    }
}


# =========================================================
# 6. 예상 검증 결과
# =========================================================
EXPECTED_RESULTS = {
    "NORMAL": {
        "status": "NORMAL",
        "changed_feature_count": 0,
        "factor_feature_count": 0
    },

    "SLIGHT": {
        "status": "SLIGHT_CHANGE",
        "changed_feature_count": 0,
        "factor_feature_count": 4
    },

    "STRONG": {
        "status": "STRONG_CHANGE",
        "changed_feature_count": 4,
        "factor_feature_count": 4
    }
}


# =========================================================
# 7. 입력 파일 확인
# =========================================================
if not VIDEO_PATH.exists():
    raise FileNotFoundError(
        "기준 영상 파일을 찾을 수 없습니다.\n"
        f"{VIDEO_PATH}"
    )

if not BASELINE_PATH.exists():
    raise FileNotFoundError(
        "Baseline CSV를 찾을 수 없습니다.\n"
        f"{BASELINE_PATH}\n\n"
        "먼저 build_baseline.py를 실행해주세요."
    )


# =========================================================
# 8. Baseline 읽기
# =========================================================
def load_baseline(
    baseline_path
):
    baseline = {}

    with open(
        baseline_path,
        "r",
        encoding="utf-8"
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
                "Baseline CSV에 필요한 컬럼이 "
                "없습니다.\n"
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
# 9. 시나리오별 현재 피처 생성
# =========================================================
def generate_current_features(
    baseline,
    scenario_z_scores
):
    current_features = {}

    for feature_name in FEATURE_NAMES:
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

        target_z_score = (
            scenario_z_scores[
                feature_name
            ]
        )

        current_value = (
            baseline_mean
            + target_z_score
            * baseline_std
        )

        # stationary_ratio는 0~1 범위
        if feature_name == "stationary_ratio":
            current_value = min(
                1.0,
                max(
                    0.0,
                    current_value
                )
            )

        # 나머지 피처는 음수가 될 수 없음
        else:
            current_value = max(
                0.0,
                current_value
            )

        current_features[feature_name] = (
            current_value
        )

    return current_features


# =========================================================
# 10. Z-score 계산
# =========================================================
def calculate_z_score(
    current,
    baseline_mean,
    baseline_std
):
    if baseline_std <= 1e-8:
        if math.isclose(
            current,
            baseline_mean,
            rel_tol=1e-9,
            abs_tol=1e-9
        ):
            return 0.0

        if current > baseline_mean:
            return MAX_Z_FOR_SCORE

        return -MAX_Z_FOR_SCORE

    return (
        current
        - baseline_mean
    ) / baseline_std


# =========================================================
# 11. 변화 방향
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
# 12. 피처별 변화 단계
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
# 13. 피처별 변화 분석
# =========================================================
def analyze_features(
    current_features,
    baseline
):
    feature_results = []

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

        absolute_z_score = abs(
            z_score
        )

        feature_results.append({
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
                get_direction(
                    current_value,
                    baseline_mean
                ),

            "change_level":
                get_change_level(
                    absolute_z_score
                ),

            "is_changed": (
                absolute_z_score
                >= CHANGE_Z_THRESHOLD
            ),

            "is_factor": (
                absolute_z_score
                >= FACTOR_Z_THRESHOLD
            )
        })

    return feature_results


# =========================================================
# 14. 종합 변화 점수
# =========================================================
def calculate_change_score(
    feature_results
):
    normalized_scores = []

    for result in feature_results:
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
        return 0.0

    average_score = (
        sum(normalized_scores)
        / len(normalized_scores)
    )

    return (
        average_score
        * 100
    )


# =========================================================
# 15. 종합 상태 판정
# =========================================================
def get_overall_status(
    change_score
):
    if change_score < 25:
        return "NORMAL"

    if change_score < 50:
        return "SLIGHT_CHANGE"

    if change_score < 75:
        return "CHANGE"

    return "STRONG_CHANGE"


# =========================================================
# 16. 주요 변화 요인
# =========================================================
def get_major_factors(
    feature_results,
    top_n=3
):
    factors = [
        result
        for result in feature_results
        if result["is_factor"]
    ]

    factors.sort(
        key=lambda item:
            item["abs_z"],
        reverse=True
    )

    return factors[:top_n]


# =========================================================
# 17. 단일 시나리오 검증
# =========================================================
def validate_scenario(
    scenario_name,
    scenario_z_scores,
    baseline
):
    current_features = (
        generate_current_features(
            baseline,
            scenario_z_scores
        )
    )

    feature_results = (
        analyze_features(
            current_features,
            baseline
        )
    )

    change_score = (
        calculate_change_score(
            feature_results
        )
    )

    overall_status = (
        get_overall_status(
            change_score
        )
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

    major_factors = get_major_factors(
        feature_results
    )

    expected = (
        EXPECTED_RESULTS[
            scenario_name
        ]
    )

    status_passed = (
        overall_status
        == expected["status"]
    )

    changed_count_passed = (
        changed_feature_count
        == expected[
            "changed_feature_count"
        ]
    )

    factor_count_passed = (
        factor_feature_count
        == expected[
            "factor_feature_count"
        ]
    )

    validation_passed = (
        status_passed
        and changed_count_passed
        and factor_count_passed
    )

    return {
        "scenario":
            scenario_name,

        "current_features":
            current_features,

        "feature_results":
            feature_results,

        "change_score":
            change_score,

        "overall_status":
            overall_status,

        "changed_feature_count":
            changed_feature_count,

        "factor_feature_count":
            factor_feature_count,

        "major_factors":
            major_factors,

        "expected_status":
            expected["status"],

        "expected_changed_count":
            expected[
                "changed_feature_count"
            ],

        "expected_factor_count":
            expected[
                "factor_feature_count"
            ],

        "validation_passed":
            validation_passed
    }


# =========================================================
# 18. Baseline 불러오기 및 전체 검증
# =========================================================
baseline = load_baseline(
    BASELINE_PATH
)

validation_results = []

for (
    scenario_name,
    scenario_z_scores
) in VALIDATION_SCENARIOS.items():

    result = validate_scenario(
        scenario_name,
        scenario_z_scores,
        baseline
    )

    validation_results.append(
        result
    )


# =========================================================
# 19. 상세 검증 결과 CSV 저장
# =========================================================
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    DETAIL_OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:
    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "scenario",
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

    for validation in validation_results:
        for result in validation[
            "feature_results"
        ]:
            writer.writerow([
                validation["scenario"],
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

                round(
                    result["z_score"],
                    6
                ),

                result["direction"],
                result["change_level"],
                result["is_changed"],
                result["is_factor"]
            ])


# =========================================================
# 20. 요약 검증 결과 CSV 저장
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
        "video",
        "scenario",
        "change_score",
        "actual_status",
        "expected_status",
        "changed_feature_count",
        "expected_changed_count",
        "factor_feature_count",
        "expected_factor_count",
        "validation_passed"
    ])

    for validation in validation_results:
        writer.writerow([
            VIDEO_PATH.name,
            validation["scenario"],

            round(
                validation["change_score"],
                2
            ),

            validation["overall_status"],
            validation["expected_status"],

            validation[
                "changed_feature_count"
            ],

            validation[
                "expected_changed_count"
            ],

            validation[
                "factor_feature_count"
            ],

            validation[
                "expected_factor_count"
            ],

            validation[
                "validation_passed"
            ]
        ])


# =========================================================
# 21. 터미널 출력
# =========================================================
print()
print("=" * 60)
print("CHANGE DETECTION VALIDATION")
print("=" * 60)

print(
    f"Reference Video : "
    f"{VIDEO_PATH.name}"
)

print(
    f"Baseline CSV    : "
    f"{BASELINE_PATH.name}"
)

print()
print("-" * 60)
print("BASELINE")
print("-" * 60)

for feature_name in FEATURE_NAMES:
    print(
        f"{feature_name:<18}: "
        f"{baseline[feature_name]['mean']:.6f}"
        f" ± "
        f"{baseline[feature_name]['std']:.6f}"
    )

for validation in validation_results:
    print()
    print("=" * 60)

    print(
        f"SCENARIO - "
        f"{validation['scenario']}"
    )

    print("=" * 60)

    for result in validation[
        "feature_results"
    ]:
        print(
            f"{result['feature']}"
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
            f"  z-score   : "
            f"{result['z_score']:.3f}"
        )

        print(
            f"  direction : "
            f"{result['direction']}"
        )

        print(
            f"  level     : "
            f"{result['change_level']}"
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

    print(
        f"Change Score     : "
        f"{validation['change_score']:.2f} / 100"
    )

    print(
        f"Actual Status    : "
        f"{validation['overall_status']}"
    )

    print(
        f"Expected Status  : "
        f"{validation['expected_status']}"
    )

    print(
        f"Changed Features : "
        f"{validation['changed_feature_count']}"
    )

    print(
        f"Factor Features  : "
        f"{validation['factor_feature_count']}"
    )

    print(
        f"Validation       : "
        f"{'PASS' if validation['validation_passed'] else 'FAIL'}"
    )

    print()
    print("Major Factors:")

    if len(
        validation["major_factors"]
    ) == 0:
        print(
            "  None"
        )

    else:
        for rank, factor in enumerate(
            validation["major_factors"],
            start=1
        ):
            print(
                f"  {rank}. "
                f"{factor['feature']} "
                f"({factor['direction']}) "
                f"| z="
                f"{factor['z_score']:.3f}"
            )


# =========================================================
# 22. 최종 검증 판정
# =========================================================
all_passed = all(
    validation["validation_passed"]
    for validation in validation_results
)

print()
print("=" * 60)
print("FINAL VALIDATION RESULT")
print("=" * 60)

print(
    f"Normal Scenario : "
    f"{'PASS' if validation_results[0]['validation_passed'] else 'FAIL'}"
)

print(
    f"Slight Scenario : "
    f"{'PASS' if validation_results[1]['validation_passed'] else 'FAIL'}"
)

print(
    f"Strong Scenario : "
    f"{'PASS' if validation_results[2]['validation_passed'] else 'FAIL'}"
)

print(
    f"Overall Result   : "
    f"{'PASS' if all_passed else 'FAIL'}"
)

print()
print(
    f"Detail CSV : "
    f"{DETAIL_OUTPUT_PATH}"
)

print(
    f"Summary CSV: "
    f"{SUMMARY_OUTPUT_PATH}"
)


# 검증 실패 시 운영체제에 실패 코드 반환
if not all_passed:
    sys.exit(1)