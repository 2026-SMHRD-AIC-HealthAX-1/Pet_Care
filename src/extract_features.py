import bisect
import csv
import math
import sys
from pathlib import Path

import cv2


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
# 2. 입력 영상 결정
# =========================================================
# 사용 예시
#
# python src/extract_features.py \
#     data/videos/cat_tracking_test.mp4
#
# python src/extract_features.py \
#     data/videos/cat_tracking_test2.mp4
#
# python src/extract_features.py \
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


# =========================================================
# 3. 영상별 입출력 경로
# =========================================================
VIDEO_NAME = VIDEO_PATH.stem

TRACKING_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking.csv"
)

QUALITY_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking_quality.csv"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_features.csv"
)

INTERVAL_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_features_by_interval.csv"
)


# =========================================================
# 4. 피처 계산 설정
# =========================================================

# 현재 좌표와 비교할 이전 좌표의 시간 간격
#
# 직전 프레임 비교가 아니라
# 1초 전 위치와 비교하여 탐지 박스 흔들림을 줄인다.
MOVEMENT_WINDOW_SECONDS = 1.0


# 목표 시간과 실제 Tracking 시간의 허용 오차
#
# 예:
# 현재 시간이 5초라면 약 4초 부근의 좌표를 찾는다.
WINDOW_TOLERANCE_SECONDS = 0.15


# 움직임 판정 기준
#
# 1초 동안 화면 대각선 대비
# 정규화 속도가 0.04 이상일 때 이동으로 판단한다.
MOVING_SPEED_THRESHOLD = 0.04


# 피처 집계 단위
AGGREGATION_SECONDS = 5


# 누락 구간을 이동거리로 연결하지 않기 위한 기준
MAX_INTEGRATION_GAP_SECONDS = 0.25


# =========================================================
# 5. 거리 계산
# =========================================================
def calculate_distance(
    x1,
    y1,
    x2,
    y2
):
    return math.sqrt(
        (x2 - x1) ** 2
        + (y2 - y1) ** 2
    )


# =========================================================
# 6. Tracking 품질 결과 읽기
# =========================================================
def load_tracking_quality(
    quality_path
):
    if not quality_path.exists():
        raise FileNotFoundError(
            "Tracking 품질 파일을 찾을 수 없습니다.\n"
            f"{quality_path}\n\n"
            "먼저 track_pet.py를 실행해주세요."
        )

    with open(
        quality_path,
        "r",
        encoding="utf-8"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        rows = list(
            reader
        )

    if len(rows) == 0:
        raise ValueError(
            "Tracking 품질 파일에 "
            "데이터가 없습니다."
        )

    row = rows[0]

    analysis_allowed = (
        row["analysis_allowed"]
        .strip()
        .lower()
        == "true"
    )

    return {
        "video":
            row.get(
                "video",
                VIDEO_PATH.name
            ),

        "tracking_quality":
            row["tracking_quality"],

        "detection_rate":
            float(
                row["detection_rate"]
            ),

        "interpolation_ratio":
            float(
                row["interpolation_ratio"]
            ),

        "missing_ratio":
            float(
                row["missing_ratio"]
            ),

        "analysis_allowed":
            analysis_allowed
    }


# =========================================================
# 7. Tracking CSV 읽기
# =========================================================
def load_tracking_data(
    tracking_path
):
    tracking_data = []

    with open(
        tracking_path,
        "r",
        encoding="utf-8"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        required_columns = {
            "frame",
            "time_sec",
            "center_x",
            "center_y",
            "status"
        }

        if reader.fieldnames is None:
            raise ValueError(
                "Tracking CSV의 헤더를 "
                "읽을 수 없습니다."
            )

        missing_columns = (
            required_columns
            - set(reader.fieldnames)
        )

        if len(missing_columns) > 0:
            raise ValueError(
                "Tracking CSV에 필요한 컬럼이 "
                "없습니다.\n"
                f"누락 컬럼: "
                f"{sorted(missing_columns)}"
            )

        for row in reader:
            center_x = None
            center_y = None

            if (
                row["center_x"] != ""
                and row["center_y"] != ""
            ):
                center_x = float(
                    row["center_x"]
                )

                center_y = float(
                    row["center_y"]
                )

            tracking_data.append({
                "frame":
                    int(
                        row["frame"]
                    ),

                "time_sec":
                    float(
                        row["time_sec"]
                    ),

                "center_x":
                    center_x,

                "center_y":
                    center_y,

                "status":
                    row["status"]
            })

    return tracking_data


# =========================================================
# 8. 목표 시간과 가장 가까운 이전 좌표 찾기
# =========================================================
def find_previous_row(
    rows,
    times,
    current_index,
    target_time
):
    insertion_index = bisect.bisect_left(
        times,
        target_time,
        0,
        current_index
    )

    # 목표 시간 주변의 여러 행을 확인한다.
    #
    # 특정 프레임이 Missing인 경우
    # 바로 주변의 유효한 좌표를 찾기 위함이다.
    search_start = max(
        0,
        insertion_index - 4
    )

    search_end = min(
        current_index,
        insertion_index + 4
    )

    candidates = []

    for index in range(
        search_start,
        search_end
    ):
        row = rows[index]

        if (
            row["center_x"] is None
            or row["center_y"] is None
        ):
            continue

        time_difference = abs(
            row["time_sec"]
            - target_time
        )

        if (
            time_difference
            <= WINDOW_TOLERANCE_SECONDS
        ):
            candidates.append({
                "row":
                    row,

                "time_difference":
                    time_difference
            })

    if len(candidates) == 0:
        return None

    selected = min(
        candidates,
        key=lambda item:
            item["time_difference"]
    )

    return selected["row"]


# =========================================================
# 9. 1초 Rolling 이동 데이터 계산
# =========================================================
def calculate_rolling_movements(
    rows,
    frame_diagonal
):
    times = [
        row["time_sec"]
        for row in rows
    ]

    movement_data = []

    for current_index in range(
        len(rows)
    ):
        current = rows[
            current_index
        ]

        if (
            current["center_x"] is None
            or current["center_y"] is None
        ):
            continue

        target_time = (
            current["time_sec"]
            - MOVEMENT_WINDOW_SECONDS
        )

        if target_time < times[0]:
            continue

        previous = find_previous_row(
            rows,
            times,
            current_index,
            target_time
        )

        if previous is None:
            continue

        delta_time = (
            current["time_sec"]
            - previous["time_sec"]
        )

        minimum_window = (
            MOVEMENT_WINDOW_SECONDS
            - WINDOW_TOLERANCE_SECONDS
        )

        maximum_window = (
            MOVEMENT_WINDOW_SECONDS
            + WINDOW_TOLERANCE_SECONDS
        )

        if not (
            minimum_window
            <= delta_time
            <= maximum_window
        ):
            continue

        distance_px = calculate_distance(
            previous["center_x"],
            previous["center_y"],
            current["center_x"],
            current["center_y"]
        )

        distance_normalized = (
            distance_px
            / frame_diagonal
        )

        speed_normalized = (
            distance_normalized
            / delta_time
        )

        is_moving = (
            speed_normalized
            >= MOVING_SPEED_THRESHOLD
        )

        # 기준 이하 움직임은 Detection 박스 흔들림으로 간주
        effective_speed = (
            speed_normalized
            if is_moving
            else 0.0
        )

        movement_data.append({
            "frame":
                current["frame"],

            "time_sec":
                current["time_sec"],

            "window_start_sec":
                previous["time_sec"],

            "window_duration_sec":
                delta_time,

            "distance_normalized":
                distance_normalized,

            "speed_normalized":
                speed_normalized,

            "effective_speed":
                effective_speed,

            "is_moving":
                is_moving
        })

    return movement_data


# =========================================================
# 10. 한 구간의 네 가지 피처 계산
# =========================================================
def calculate_features(
    movements
):
    if len(movements) == 0:
        return {
            "activity_level": 0.0,
            "stationary_ratio": 0.0,
            "travel_distance": 0.0,
            "moving_speed": 0.0,
            "moving_count": 0,
            "stationary_count": 0,
            "measurement_count": 0,
            "analyzed_duration": 0.0
        }

    effective_speeds = [
        movement["effective_speed"]
        for movement in movements
    ]

    moving_speeds = [
        movement["speed_normalized"]
        for movement in movements
        if movement["is_moving"]
    ]

    moving_count = sum(
        1
        for movement in movements
        if movement["is_moving"]
    )

    stationary_count = (
        len(movements)
        - moving_count
    )

    activity_level = (
        sum(effective_speeds)
        / len(effective_speeds)
    )

    stationary_ratio = (
        stationary_count
        / len(movements)
    )

    # -----------------------------------------------------
    # 이동거리 계산
    #
    # Rolling 속도를 시간에 대해 적분한다.
    # 긴 Missing 구간은 서로 연결하지 않는다.
    # -----------------------------------------------------
    travel_distance = 0.0

    for index in range(
        1,
        len(movements)
    ):
        previous = movements[
            index - 1
        ]

        current = movements[
            index
        ]

        integration_time = (
            current["time_sec"]
            - previous["time_sec"]
        )

        if (
            integration_time <= 0
            or integration_time
            > MAX_INTEGRATION_GAP_SECONDS
        ):
            continue

        average_effective_speed = (
            previous["effective_speed"]
            + current["effective_speed"]
        ) / 2

        travel_distance += (
            average_effective_speed
            * integration_time
        )

    if len(moving_speeds) > 0:
        moving_speed = (
            sum(moving_speeds)
            / len(moving_speeds)
        )
    else:
        moving_speed = 0.0

    if len(movements) >= 2:
        analyzed_duration = (
            movements[-1]["time_sec"]
            - movements[0]["time_sec"]
        )
    else:
        analyzed_duration = 0.0

    return {
        "activity_level":
            activity_level,

        "stationary_ratio":
            stationary_ratio,

        "travel_distance":
            travel_distance,

        "moving_speed":
            moving_speed,

        "moving_count":
            moving_count,

        "stationary_count":
            stationary_count,

        "measurement_count":
            len(movements),

        "analyzed_duration":
            analyzed_duration
    }


# =========================================================
# 11. 입력 파일 확인
# =========================================================
if not VIDEO_PATH.exists():
    raise FileNotFoundError(
        "영상 파일을 찾을 수 없습니다.\n"
        f"{VIDEO_PATH}"
    )

if not TRACKING_PATH.exists():
    raise FileNotFoundError(
        "Tracking CSV 파일을 찾을 수 없습니다.\n"
        f"{TRACKING_PATH}\n\n"
        "먼저 track_pet.py를 실행해주세요."
    )


# =========================================================
# 12. Tracking 품질 확인
# =========================================================
quality = load_tracking_quality(
    QUALITY_PATH
)

print()
print("=" * 55)
print("TRACKING QUALITY CHECK")
print("=" * 55)

print(
    f"Video               : "
    f"{quality['video']}"
)

print(
    f"Detection Rate      : "
    f"{quality['detection_rate'] * 100:.2f}%"
)

print(
    f"Interpolation Ratio : "
    f"{quality['interpolation_ratio'] * 100:.2f}%"
)

print(
    f"Missing Ratio       : "
    f"{quality['missing_ratio'] * 100:.2f}%"
)

print(
    f"Tracking Quality    : "
    f"{quality['tracking_quality']}"
)

print(
    f"Analysis Allowed    : "
    f"{quality['analysis_allowed']}"
)

if not quality["analysis_allowed"]:
    raise RuntimeError(
        "Tracking 품질이 LOW_QUALITY이므로 "
        "피처 추출을 진행할 수 없습니다."
    )


# =========================================================
# 13. 영상 정보 확인
# =========================================================
capture = cv2.VideoCapture(
    str(VIDEO_PATH)
)

if not capture.isOpened():
    raise ValueError(
        "영상 파일을 열 수 없습니다.\n"
        f"{VIDEO_PATH}"
    )

frame_width = int(
    capture.get(
        cv2.CAP_PROP_FRAME_WIDTH
    )
)

frame_height = int(
    capture.get(
        cv2.CAP_PROP_FRAME_HEIGHT
    )
)

fps = capture.get(
    cv2.CAP_PROP_FPS
)

capture.release()

if (
    frame_width <= 0
    or frame_height <= 0
):
    raise ValueError(
        "영상 해상도를 읽을 수 없습니다."
    )

if fps <= 0:
    raise ValueError(
        "영상 FPS를 읽을 수 없습니다."
    )

frame_diagonal = math.sqrt(
    frame_width ** 2
    + frame_height ** 2
)


# =========================================================
# 14. Tracking 데이터 불러오기
# =========================================================
tracking_data = load_tracking_data(
    TRACKING_PATH
)

if len(tracking_data) < 2:
    raise ValueError(
        "피처 계산을 위한 Tracking "
        "데이터가 부족합니다."
    )

video_start_time = (
    tracking_data[0]["time_sec"]
)

video_end_time = (
    tracking_data[-1]["time_sec"]
)

video_duration = (
    video_end_time
    - video_start_time
)


# =========================================================
# 15. Rolling 이동 데이터 계산
# =========================================================
movement_data = (
    calculate_rolling_movements(
        tracking_data,
        frame_diagonal
    )
)

if len(movement_data) < 2:
    raise ValueError(
        "Rolling 피처 계산을 위한 "
        "유효한 좌표 데이터가 부족합니다."
    )


# =========================================================
# 16. 전체 영상 피처 계산
# =========================================================
overall_features = calculate_features(
    movement_data
)


# =========================================================
# 17. 전체 피처 CSV 저장
# =========================================================
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:
    writer = csv.writer(
        csvfile
    )

    # 기존 baseline 코드와 호환되도록
    # 네 가지 피처 컬럼을 유지한다.
    writer.writerow([
        "activity_level",
        "stationary_ratio",
        "travel_distance",
        "moving_speed"
    ])

    writer.writerow([
        round(
            overall_features[
                "activity_level"
            ],
            6
        ),

        round(
            overall_features[
                "stationary_ratio"
            ],
            6
        ),

        round(
            overall_features[
                "travel_distance"
            ],
            6
        ),

        round(
            overall_features[
                "moving_speed"
            ],
            6
        )
    ])


# =========================================================
# 18. 구간별 Rolling 데이터 분리
# =========================================================
interval_groups = {}

for movement in movement_data:
    interval_index = int(
        movement["time_sec"]
        // AGGREGATION_SECONDS
    )

    if interval_index not in interval_groups:
        interval_groups[
            interval_index
        ] = []

    interval_groups[
        interval_index
    ].append(
        movement
    )


# =========================================================
# 19. 구간별 피처 계산
# =========================================================
interval_results = []

for interval_index in sorted(
    interval_groups.keys()
):
    movements = (
        interval_groups[
            interval_index
        ]
    )

    features = calculate_features(
        movements
    )

    interval_start = (
        interval_index
        * AGGREGATION_SECONDS
    )

    interval_end = min(
        interval_start
        + AGGREGATION_SECONDS,
        video_end_time
    )

    interval_results.append({
        "interval_start_sec":
            interval_start,

        "interval_end_sec":
            interval_end,

        "activity_level":
            features["activity_level"],

        "stationary_ratio":
            features["stationary_ratio"],

        "travel_distance":
            features["travel_distance"],

        "moving_speed":
            features["moving_speed"],

        "moving_count":
            features["moving_count"],

        "stationary_count":
            features["stationary_count"],

        "measurement_count":
            features["measurement_count"],

        "analyzed_duration":
            features["analyzed_duration"]
    })


# =========================================================
# 20. 구간별 피처 CSV 저장
# =========================================================
with open(
    INTERVAL_OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:
    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "interval_start_sec",
        "interval_end_sec",
        "activity_level",
        "stationary_ratio",
        "travel_distance",
        "moving_speed",
        "moving_count",
        "stationary_count",
        "measurement_count",
        "analyzed_duration"
    ])

    for result in interval_results:
        writer.writerow([
            round(
                result["interval_start_sec"],
                3
            ),

            round(
                result["interval_end_sec"],
                3
            ),

            round(
                result["activity_level"],
                6
            ),

            round(
                result["stationary_ratio"],
                6
            ),

            round(
                result["travel_distance"],
                6
            ),

            round(
                result["moving_speed"],
                6
            ),

            result["moving_count"],
            result["stationary_count"],
            result["measurement_count"],

            round(
                result["analyzed_duration"],
                3
            )
        ])


# =========================================================
# 21. 결과 출력
# =========================================================
print()
print("=" * 55)
print("PET FEATURE EXTRACTION - ROLLING VERSION")
print("=" * 55)

print(
    f"Video            : "
    f"{VIDEO_PATH.name}"
)

print(
    f"Video Path       : "
    f"{VIDEO_PATH}"
)

print(
    f"Tracking CSV     : "
    f"{TRACKING_PATH.name}"
)

print(
    f"Resolution       : "
    f"{frame_width} x {frame_height}"
)

print(
    f"FPS              : "
    f"{fps:.3f}"
)

print(
    f"Video Duration   : "
    f"{video_duration:.2f} sec"
)

print(
    f"Movement Window  : "
    f"{MOVEMENT_WINDOW_SECONDS:.2f} sec"
)

print(
    f"Movement Threshold: "
    f"{MOVING_SPEED_THRESHOLD:.3f}"
)

print(
    f"Aggregation      : "
    f"{AGGREGATION_SECONDS} sec"
)

print(
    f"Valid Measurements: "
    f"{len(movement_data)}"
)

print()
print("-" * 55)
print("OVERALL FEATURES")
print("-" * 55)

print(
    f"activity_level   : "
    f"{overall_features['activity_level']:.6f}"
)

print(
    f"stationary_ratio : "
    f"{overall_features['stationary_ratio']:.6f}"
)

print(
    f"travel_distance  : "
    f"{overall_features['travel_distance']:.6f}"
)

print(
    f"moving_speed     : "
    f"{overall_features['moving_speed']:.6f}"
)

print(
    f"moving_count     : "
    f"{overall_features['moving_count']}"
)

print(
    f"stationary_count : "
    f"{overall_features['stationary_count']}"
)

print(
    f"analyzed_duration: "
    f"{overall_features['analyzed_duration']:.3f} sec"
)

print()
print("-" * 55)
print("INTERVAL FEATURES")
print("-" * 55)

for result in interval_results:
    print(
        f"{result['interval_start_sec']:.2f}"
        f" ~ "
        f"{result['interval_end_sec']:.2f} sec"
    )

    print(
        f"  activity_level   : "
        f"{result['activity_level']:.6f}"
    )

    print(
        f"  stationary_ratio : "
        f"{result['stationary_ratio']:.6f}"
    )

    print(
        f"  travel_distance  : "
        f"{result['travel_distance']:.6f}"
    )

    print(
        f"  moving_speed     : "
        f"{result['moving_speed']:.6f}"
    )

    print(
        f"  moving_count     : "
        f"{result['moving_count']}"
    )

    print(
        f"  stationary_count : "
        f"{result['stationary_count']}"
    )

    print(
        f"  measurements     : "
        f"{result['measurement_count']}"
    )

    print(
        f"  analyzed_duration: "
        f"{result['analyzed_duration']:.3f} sec"
    )

    print()

print("=" * 55)
print("FEATURE EXTRACTION COMPLETE")
print("=" * 55)

print(
    f"Overall CSV : "
    f"{OUTPUT_PATH}"
)

print(
    f"Interval CSV: "
    f"{INTERVAL_OUTPUT_PATH}"
)