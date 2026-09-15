import csv
import random
import sys
from pathlib import Path
from statistics import mean, stdev


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
# 2. 기준 영상 결정
# =========================================================
# 사용 예시
#
# python src/build_baseline.py \
#     data/videos/cat_tracking_test3.mov
#
# 입력값이 없으면 기존 강아지 테스트 영상을 사용한다.
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


# =========================================================
# 3. 영상별 입출력 경로
# =========================================================
VIDEO_NAME = VIDEO_PATH.stem

INTERVAL_FEATURE_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_features_by_interval.csv"
)

SOURCE_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_baseline_source_7days.csv"
)

BASELINE_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_baseline_features.csv"
)


# =========================================================
# 4. Baseline 설정
# =========================================================

# 피처 추출 단계의 집계 단위
AGGREGATION_SECONDS = 5.0


# 완전한 5초 구간으로 인정할 최소 분석 시간
#
# 5초의 90%인 4.5초 이상 분석된 구간만 사용한다.
MIN_COMPLETE_INTERVAL_RATIO = 0.90

MIN_COMPLETE_INTERVAL_SECONDS = (
    AGGREGATION_SECONDS
    * MIN_COMPLETE_INTERVAL_RATIO
)


# Baseline 구성 일수
BASELINE_DAYS = 7


# 같은 실행 결과를 재현하기 위한 난수 seed
RANDOM_SEED = 42


# 실제 피처를 중심으로 적용할 정상 변동 범위
#
# 현재는 기술 검증용 합성 Baseline이며,
# 동일 개체의 장기 데이터가 확보되면
# 실제 데이터 기반 계산으로 교체한다.
SYNTHETIC_VARIATION = {
    "activity_level": 0.08,
    "stationary_ratio": 0.06,
    "travel_distance": 0.08,
    "moving_speed": 0.07
}


# 분석 대상 피처
FEATURE_NAMES = [
    "activity_level",
    "stationary_ratio",
    "travel_distance",
    "moving_speed"
]


# =========================================================
# 5. 입력 파일 확인
# =========================================================
if not VIDEO_PATH.exists():
    raise FileNotFoundError(
        "기준 영상 파일을 찾을 수 없습니다.\n"
        f"{VIDEO_PATH}"
    )

if not INTERVAL_FEATURE_PATH.exists():
    raise FileNotFoundError(
        "구간별 Feature CSV를 찾을 수 없습니다.\n"
        f"{INTERVAL_FEATURE_PATH}\n\n"
        "먼저 다음 명령을 실행해주세요.\n"
        f"python src/extract_features.py "
        f"data/videos/{VIDEO_PATH.name}"
    )


# =========================================================
# 6. 구간별 Feature CSV 읽기
# =========================================================
def load_interval_features(
    interval_feature_path
):
    interval_records = []

    with open(
        interval_feature_path,
        "r",
        encoding="utf-8"
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
                "구간별 Feature CSV의 헤더를 "
                "읽을 수 없습니다."
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
# 7. 완전한 분석 구간 선택
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
            "Baseline 생성에 사용할 수 있는 "
            "완전한 5초 구간이 없습니다.\n"
            f"필요 분석 시간: "
            f"{MIN_COMPLETE_INTERVAL_SECONDS:.2f}초 이상"
        )

    return complete_intervals


# =========================================================
# 8. 기준 피처 계산
# =========================================================
# 완전한 5초 구간들의 평균값을
# 해당 영상의 기준 피처로 사용한다.
# =========================================================
def calculate_reference_features(
    complete_intervals
):
    reference_features = {}

    for feature_name in FEATURE_NAMES:
        feature_values = [
            record[feature_name]
            for record in complete_intervals
        ]

        reference_features[feature_name] = mean(
            feature_values
        )

    return reference_features


# =========================================================
# 9. 7일 합성 Baseline 원천 데이터 생성
# =========================================================
def generate_baseline_source(
    reference_features
):
    random.seed(
        RANDOM_SEED
    )

    records = []

    for day in range(
        1,
        BASELINE_DAYS + 1
    ):
        record = {
            "day": day
        }

        for (
            feature_name,
            base_value
        ) in reference_features.items():

            variation_rate = (
                SYNTHETIC_VARIATION[
                    feature_name
                ]
            )

            variation = random.uniform(
                -variation_rate,
                variation_rate
            )

            generated_value = (
                base_value
                * (1 + variation)
            )

            # stationary_ratio는 0~1 범위로 제한
            if (
                feature_name
                == "stationary_ratio"
            ):
                generated_value = min(
                    1.0,
                    max(
                        0.0,
                        generated_value
                    )
                )

            # 나머지 피처는 음수가 될 수 없음
            else:
                generated_value = max(
                    0.0,
                    generated_value
                )

            record[feature_name] = (
                generated_value
            )

        records.append(
            record
        )

    return records


# =========================================================
# 10. 7일 합성 원천 데이터 저장
# =========================================================
def save_baseline_source(
    records
):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        SOURCE_OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:
        writer = csv.writer(
            csvfile
        )

        writer.writerow([
            "day",
            "activity_level",
            "stationary_ratio",
            "travel_distance",
            "moving_speed"
        ])

        for record in records:
            writer.writerow([
                record["day"],

                round(
                    record["activity_level"],
                    6
                ),

                round(
                    record["stationary_ratio"],
                    6
                ),

                round(
                    record["travel_distance"],
                    6
                ),

                round(
                    record["moving_speed"],
                    6
                )
            ])


# =========================================================
# 11. Baseline 평균·표준편차 계산
# =========================================================
def build_baseline(
    records
):
    baseline = {}

    for feature_name in FEATURE_NAMES:
        feature_values = [
            record[feature_name]
            for record in records
        ]

        baseline[feature_name] = {
            "mean":
                mean(
                    feature_values
                ),

            "std":
                stdev(
                    feature_values
                )
        }

    return baseline


# =========================================================
# 12. Baseline 결과 저장
# =========================================================
def save_baseline(
    baseline
):
    with open(
        BASELINE_OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:
        writer = csv.writer(
            csvfile
        )

        writer.writerow([
            "feature",
            "mean",
            "std"
        ])

        for feature_name in FEATURE_NAMES:
            values = baseline[
                feature_name
            ]

            writer.writerow([
                feature_name,

                round(
                    values["mean"],
                    6
                ),

                round(
                    values["std"],
                    6
                )
            ])


# =========================================================
# 13. 프로그램 실행
# =========================================================
interval_records = load_interval_features(
    INTERVAL_FEATURE_PATH
)

complete_intervals = select_complete_intervals(
    interval_records
)

reference_features = (
    calculate_reference_features(
        complete_intervals
    )
)

baseline_source = (
    generate_baseline_source(
        reference_features
    )
)

save_baseline_source(
    baseline_source
)

baseline = build_baseline(
    baseline_source
)

save_baseline(
    baseline
)


# =========================================================
# 14. 결과 출력
# =========================================================
print()
print("=" * 55)
print("PET BASELINE BUILD")
print("=" * 55)

print(
    f"Reference Video    : "
    f"{VIDEO_PATH.name}"
)

print(
    f"Interval CSV       : "
    f"{INTERVAL_FEATURE_PATH.name}"
)

print(
    f"Total Intervals    : "
    f"{len(interval_records)}"
)

print(
    f"Complete Intervals : "
    f"{len(complete_intervals)}"
)

print(
    f"Minimum Duration   : "
    f"{MIN_COMPLETE_INTERVAL_SECONDS:.2f} sec"
)

print()
print("-" * 55)
print("SELECTED INTERVALS")
print("-" * 55)

for record in complete_intervals:
    print(
        f"{record['interval_start_sec']:.2f}"
        f" ~ "
        f"{record['interval_end_sec']:.2f} sec"
        f" | analyzed "
        f"{record['analyzed_duration']:.3f} sec"
    )

print()
print("-" * 55)
print("REFERENCE FEATURES")
print("-" * 55)

for feature_name in FEATURE_NAMES:
    print(
        f"{feature_name:<18}: "
        f"{reference_features[feature_name]:.6f}"
    )

print()
print("-" * 55)
print("7-DAY SYNTHETIC BASELINE SOURCE")
print("-" * 55)

for record in baseline_source:
    print(
        f"Day {record['day']}"
    )

    print(
        f"  activity_level   : "
        f"{record['activity_level']:.6f}"
    )

    print(
        f"  stationary_ratio : "
        f"{record['stationary_ratio']:.6f}"
    )

    print(
        f"  travel_distance  : "
        f"{record['travel_distance']:.6f}"
    )

    print(
        f"  moving_speed     : "
        f"{record['moving_speed']:.6f}"
    )

print()
print("-" * 55)
print("BASELINE MEAN AND STANDARD DEVIATION")
print("-" * 55)

for feature_name in FEATURE_NAMES:
    values = baseline[
        feature_name
    ]

    print(
        f"{feature_name:<18}: "
        f"{values['mean']:.6f}"
        f" ± "
        f"{values['std']:.6f}"
    )

print()
print("=" * 55)
print("BASELINE BUILD COMPLETE")
print("=" * 55)

print(
    f"Source CSV  : "
    f"{SOURCE_OUTPUT_PATH}"
)

print(
    f"Baseline CSV: "
    f"{BASELINE_OUTPUT_PATH}"
)