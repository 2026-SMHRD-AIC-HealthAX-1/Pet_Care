import csv
import sys
from collections import deque
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

PREVIEW_DIR = (
    OUTPUT_DIR
    / "previews"
)


# =========================================================
# 2. 입력 영상 결정
# =========================================================
# 사용 예시
#
# python src/create_tracking_preview.py \
#     data/videos/pet_tracking_test.mp4
#
# python src/create_tracking_preview.py \
#     data/videos/cat_tracking_test3.mov
# =========================================================
if len(sys.argv) < 2:
    raise ValueError(
        "미리보기를 생성할 영상을 입력해주세요.\n\n"
        "예시:\n"
        "python src/create_tracking_preview.py "
        "data/videos/pet_tracking_test.mp4"
    )

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

VIDEO_PATH = VIDEO_PATH.resolve()
VIDEO_NAME = VIDEO_PATH.stem


# =========================================================
# 3. 입출력 경로
# =========================================================
TRACKING_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking.csv"
)

QUALITY_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking_quality.csv"
)

FEATURE_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_features.csv"
)

CHANGE_SUMMARY_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_change_summary.csv"
)

PREVIEW_PATH = (
    PREVIEW_DIR
    / f"{VIDEO_NAME}_tracking_preview.mp4"
)


# =========================================================
# 4. 미리보기 설정
# =========================================================
MAX_PREVIEW_WIDTH = 1280
TRAIL_SECONDS = 3.0

FONT = cv2.FONT_HERSHEY_SIMPLEX


# =========================================================
# 5. 파일 확인
# =========================================================
required_files = [
    VIDEO_PATH,
    TRACKING_PATH,
    QUALITY_PATH,
    FEATURE_PATH
]

for required_path in required_files:
    if not required_path.exists():
        raise FileNotFoundError(
            "필요한 파일을 찾을 수 없습니다.\n"
            f"{required_path}"
        )


# =========================================================
# 6. CSV 첫 번째 행 읽기
# =========================================================
def load_first_row(
    csv_path
):
    if not csv_path.exists():
        return {}

    with open(
        csv_path,
        "r",
        encoding="utf-8"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        for row in reader:
            return row

    return {}


# =========================================================
# 7. Tracking CSV 읽기
# =========================================================
def load_tracking_data(
    tracking_path
):
    tracking_data = {}
    pet_type = "unknown"

    with open(
        tracking_path,
        "r",
        encoding="utf-8"
    ) as csvfile:
        reader = csv.DictReader(
            csvfile
        )

        for row in reader:
            frame_number = int(
                row["frame"]
            )

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

            if (
                pet_type == "unknown"
                and row.get("pet_type", "") != ""
            ):
                pet_type = row["pet_type"]

            tracking_data[frame_number] = {
                "center_x":
                    center_x,

                "center_y":
                    center_y,

                "status":
                    row.get(
                        "status",
                        "unknown"
                    ),

                "confidence":
                    row.get(
                        "confidence",
                        ""
                    )
            }

    return tracking_data, pet_type


# =========================================================
# 8. 숫자 안전 변환
# =========================================================
def safe_float(
    value,
    default=0.0
):
    try:
        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):
        return default


# =========================================================
# 9. 반투명 정보 패널
# =========================================================
def draw_panel(
    frame,
    x1,
    y1,
    x2,
    y2,
    opacity=0.65
):
    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (x1, y1),
        (x2, y2),
        (15, 20, 30),
        -1
    )

    cv2.addWeighted(
        overlay,
        opacity,
        frame,
        1 - opacity,
        0,
        frame
    )


# =========================================================
# 10. 텍스트 출력
# =========================================================
def draw_text(
    frame,
    text,
    position,
    color=(255, 255, 255),
    scale=0.62,
    thickness=1
):
    cv2.putText(
        frame,
        text,
        position,
        FONT,
        scale,
        color,
        thickness,
        cv2.LINE_AA
    )


# =========================================================
# 11. 상태별 색상
# =========================================================
def get_status_color(
    status
):
    if "jump_filtered" in status:
        return (0, 80, 255)

    if "interpolated" in status:
        return (0, 215, 255)

    if status == "detected":
        return (70, 230, 100)

    return (180, 180, 180)


# =========================================================
# 12. 데이터 불러오기
# =========================================================
tracking_data, pet_type = (
    load_tracking_data(
        TRACKING_PATH
    )
)

quality = load_first_row(
    QUALITY_PATH
)

features = load_first_row(
    FEATURE_PATH
)

change_summary = load_first_row(
    CHANGE_SUMMARY_PATH
)


tracking_quality = quality.get(
    "tracking_quality",
    "unknown"
)

detection_rate = safe_float(
    quality.get(
        "detection_rate"
    )
)

missing_ratio = safe_float(
    quality.get(
        "missing_ratio"
    )
)

activity_level = safe_float(
    features.get(
        "activity_level"
    )
)

stationary_ratio = safe_float(
    features.get(
        "stationary_ratio"
    )
)

travel_distance = safe_float(
    features.get(
        "travel_distance"
    )
)

moving_speed = safe_float(
    features.get(
        "moving_speed"
    )
)

change_status = change_summary.get(
    "status",
    "not analyzed"
)

change_score = safe_float(
    change_summary.get(
        "change_score"
    )
)


# =========================================================
# 13. 영상 열기
# =========================================================
capture = cv2.VideoCapture(
    str(VIDEO_PATH)
)

if not capture.isOpened():
    raise ValueError(
        "영상을 열 수 없습니다.\n"
        f"{VIDEO_PATH}"
    )

fps = capture.get(
    cv2.CAP_PROP_FPS
)

original_width = int(
    capture.get(
        cv2.CAP_PROP_FRAME_WIDTH
    )
)

original_height = int(
    capture.get(
        cv2.CAP_PROP_FRAME_HEIGHT
    )
)

total_frames = int(
    capture.get(
        cv2.CAP_PROP_FRAME_COUNT
    )
)

if fps <= 0:
    raise ValueError(
        "영상 FPS를 읽을 수 없습니다."
    )

if (
    original_width <= 0
    or original_height <= 0
):
    raise ValueError(
        "영상 해상도를 읽을 수 없습니다."
    )


# =========================================================
# 14. 미리보기 크기 계산
# =========================================================
resize_ratio = min(
    1.0,
    MAX_PREVIEW_WIDTH
    / original_width
)

preview_width = int(
    original_width
    * resize_ratio
)

preview_height = int(
    original_height
    * resize_ratio
)

scale_x = (
    preview_width
    / original_width
)

scale_y = (
    preview_height
    / original_height
)


# =========================================================
# 15. 출력 영상 설정
# =========================================================
PREVIEW_DIR.mkdir(
    parents=True,
    exist_ok=True
)

fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    str(PREVIEW_PATH),
    fourcc,
    fps,
    (
        preview_width,
        preview_height
    )
)

if not writer.isOpened():
    raise ValueError(
        "미리보기 영상 저장을 "
        "시작할 수 없습니다.\n"
        f"{PREVIEW_PATH}"
    )


# =========================================================
# 16. 이동 경로 저장
# =========================================================
trail_max_length = max(
    1,
    int(
        round(
            fps
            * TRAIL_SECONDS
        )
    )
)

trail_points = deque(
    maxlen=trail_max_length
)


# =========================================================
# 17. 영상 프레임 처리
# =========================================================
frame_number = 0

print()
print("=" * 55)
print("TRACKING PREVIEW GENERATION")
print("=" * 55)

print(
    f"Video       : "
    f"{VIDEO_PATH.name}"
)

print(
    f"Pet Type    : "
    f"{pet_type}"
)

print(
    f"Resolution  : "
    f"{original_width} x {original_height}"
)

print(
    f"Preview     : "
    f"{preview_width} x {preview_height}"
)

print(
    f"FPS         : "
    f"{fps:.3f}"
)

print(
    f"Total Frames: "
    f"{total_frames}"
)

print()


while True:
    success, frame = capture.read()

    if not success:
        break

    frame_number += 1

    if resize_ratio != 1.0:
        frame = cv2.resize(
            frame,
            (
                preview_width,
                preview_height
            ),
            interpolation=cv2.INTER_AREA
        )

    tracking = tracking_data.get(
        frame_number
    )

    current_status = "missing"
    confidence_text = "-"

    if tracking is not None:
        current_status = tracking[
            "status"
        ]

        if tracking["confidence"] != "":
            confidence_text = tracking[
                "confidence"
            ]

        if (
            tracking["center_x"] is not None
            and tracking["center_y"] is not None
        ):
            point_x = int(
                tracking["center_x"]
                * scale_x
            )

            point_y = int(
                tracking["center_y"]
                * scale_y
            )

            current_point = (
                point_x,
                point_y
            )

            trail_points.append(
                current_point
            )

            # 이동 경로
            if len(trail_points) >= 2:
                points = list(
                    trail_points
                )

                for index in range(
                    1,
                    len(points)
                ):
                    cv2.line(
                        frame,
                        points[index - 1],
                        points[index],
                        (255, 185, 50),
                        3,
                        cv2.LINE_AA
                    )

            point_color = get_status_color(
                current_status
            )

            # 현재 중심점 바깥 원
            cv2.circle(
                frame,
                current_point,
                11,
                (255, 255, 255),
                3
            )

            # 현재 중심점
            cv2.circle(
                frame,
                current_point,
                7,
                point_color,
                -1
            )

            draw_text(
                frame,
                pet_type.upper(),
                (
                    point_x + 15,
                    point_y - 15
                ),
                color=point_color,
                scale=0.7,
                thickness=2
            )

        else:
            trail_points.clear()

    else:
        trail_points.clear()

    current_time = (
        (frame_number - 1)
        / fps
    )

    # -----------------------------------------------------
    # 상단 패널
    # -----------------------------------------------------
    panel_width = min(
        preview_width - 30,
        570
    )

    draw_panel(
        frame,
        15,
        15,
        panel_width,
        205
    )

    draw_text(
        frame,
        "PET BEHAVIOR TRACKING PREVIEW",
        (30, 45),
        color=(100, 230, 255),
        scale=0.72,
        thickness=2
    )

    draw_text(
        frame,
        f"Video: {VIDEO_PATH.name}",
        (30, 75)
    )

    draw_text(
        frame,
        f"Pet: {pet_type.upper()}",
        (30, 103)
    )

    draw_text(
        frame,
        (
            f"Time: {current_time:.2f}s"
            f"  |  Frame: {frame_number}"
        ),
        (30, 131)
    )

    draw_text(
        frame,
        (
            f"Tracking: {current_status}"
            f"  |  Conf: {confidence_text}"
        ),
        (30, 159),
        color=get_status_color(
            current_status
        )
    )

    draw_text(
        frame,
        (
            f"Quality: {tracking_quality}"
            f"  |  Detection: "
            f"{detection_rate * 100:.1f}%"
            f"  |  Missing: "
            f"{missing_ratio * 100:.1f}%"
        ),
        (30, 187)
    )

    # -----------------------------------------------------
    # 하단 패널
    # -----------------------------------------------------
    bottom_y1 = (
        preview_height - 115
    )

    bottom_y2 = (
        preview_height - 15
    )

    draw_panel(
        frame,
        15,
        bottom_y1,
        preview_width - 15,
        bottom_y2
    )

    draw_text(
        frame,
        (
            f"Activity: {activity_level:.3f}"
            f"   Stationary: {stationary_ratio:.3f}"
            f"   Distance: {travel_distance:.3f}"
            f"   Speed: {moving_speed:.3f}"
        ),
        (
            30,
            bottom_y1 + 35
        ),
        color=(255, 255, 255),
        scale=0.66,
        thickness=2
    )

    change_color = (
        (80, 220, 100)
        if change_status == "NORMAL"
        else (0, 180, 255)
    )

    draw_text(
        frame,
        (
            f"Change Status: {change_status}"
            f"   |   Change Score: "
            f"{change_score:.2f} / 100"
        ),
        (
            30,
            bottom_y1 + 75
        ),
        color=change_color,
        scale=0.72,
        thickness=2
    )

    writer.write(
        frame
    )

    # 진행률 출력
    if (
        total_frames > 0
        and frame_number
        % max(1, total_frames // 10)
        == 0
    ):
        progress = (
            frame_number
            / total_frames
            * 100
        )

        print(
            f"Progress: "
            f"{progress:.1f}%"
        )


# =========================================================
# 18. 종료
# =========================================================
capture.release()
writer.release()

print()
print("=" * 55)
print("TRACKING PREVIEW COMPLETE")
print("=" * 55)

print(
    f"Processed Frames: "
    f"{frame_number}"
)

print(
    f"Saved Video    : "
    f"{PREVIEW_PATH}"
)