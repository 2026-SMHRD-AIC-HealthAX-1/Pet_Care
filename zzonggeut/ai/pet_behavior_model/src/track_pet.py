from ultralytics import YOLO
import cv2
import csv
import math
import sys
from pathlib import Path
from collections import Counter


# =========================================================
# 1. 프로젝트 경로
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# 2. 입력 영상 결정
# =========================================================
# 실행 예시
#
# 고양이:
# python src/track_pet.py \
#     data/videos/cat_tracking_test.mp4 cat
#
# 강아지:
# python src/track_pet.py \
#     data/videos/pet_tracking_test.mp4 dog
#
# 종을 생략하면 YOLO 예측 결과로 종을 결정한다.
# =========================================================
if len(sys.argv) >= 2:
    input_path = Path(sys.argv[1])

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
# 3. 반려동물 클래스
# =========================================================
# COCO 클래스
# 15 = cat
# 16 = dog
# =========================================================
PET_CLASS_IDS = {
    "cat": 15,
    "dog": 16
}

PET_CLASS_NAMES = {
    15: "cat",
    16: "dog"
}


# =========================================================
# 4. 등록된 반려동물 종 결정
# =========================================================
if len(sys.argv) >= 3:
    TARGET_PET_TYPE = (
        sys.argv[2]
        .strip()
        .lower()
    )

    if TARGET_PET_TYPE not in PET_CLASS_IDS:
        raise ValueError(
            "반려동물 종류는 cat 또는 dog만 "
            "입력할 수 있습니다.\n"
            f"입력값: {TARGET_PET_TYPE}"
        )

    TARGET_CLASS_TEXT = TARGET_PET_TYPE

else:
    TARGET_PET_TYPE = None
    TARGET_CLASS_TEXT = "auto"


# =========================================================
# 5. 탐지 대상 클래스
# =========================================================
# 등록 종이 있으면 해당 YOLO class만 탐지한다.
# 종을 생략한 독립 실행에서만 cat과 dog를 모두 탐지하고,
# 첫 탐지 결과로 종을 고정하는 기존 자동 모드를 유지한다.
# =========================================================
if TARGET_PET_TYPE is not None:
    DETECTION_CLASSES = [
        PET_CLASS_IDS[TARGET_PET_TYPE]
    ]
    DETECTION_CLASS_TEXT = TARGET_PET_TYPE

else:
    DETECTION_CLASSES = sorted(
        PET_CLASS_NAMES.keys()
    )
    DETECTION_CLASS_TEXT = "cat, dog"


# =========================================================
# 6. 영상별 출력 경로
# =========================================================
# 예:
# cat_tracking_test.mp4
# → cat_tracking_test_tracking.csv
# → cat_tracking_test_tracking_quality.csv
# =========================================================
VIDEO_NAME = VIDEO_PATH.stem

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
)

TRACKING_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking.csv"
)

QUALITY_OUTPUT_PATH = (
    OUTPUT_DIR
    / f"{VIDEO_NAME}_tracking_quality.csv"
)


# =========================================================
# 7. Tracking 안정화 설정
# =========================================================

# 짧은 탐지 누락 보간 허용 시간
MAX_GAP_SECONDS = 1.0

# 화면 대각선 대비 순간 이동 허용 비율
MAX_JUMP_RATIO = 0.12

# EMA 좌표 평활화
SMOOTHING_ALPHA = 0.35


# =========================================================
# 8. YOLO 설정
# =========================================================
MODEL_PATH = "yolo11s.pt"

YOLO_IMAGE_SIZE = 960
YOLO_CONFIDENCE = 0.15
YOLO_IOU = 0.50


# =========================================================
# 9. Tracking 품질 판정 기준
# =========================================================
GOOD_DETECTION_RATE = 0.85
GOOD_MISSING_RATIO = 0.05
GOOD_INTERPOLATION_RATIO = 0.15

WARNING_DETECTION_RATE = 0.65
WARNING_MISSING_RATIO = 0.15
WARNING_INTERPOLATION_RATIO = 0.30


# =========================================================
# 10. 두 좌표 사이 거리 계산
# =========================================================
def distance(
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
# 11. 짧은 Missing 구간 보간
# =========================================================
def interpolate_short_gaps(
    records,
    max_gap_frames
):
    index = 0

    while index < len(records):

        if records[index]["raw_x"] is not None:
            index += 1
            continue

        gap_start = index

        while (
            index < len(records)
            and records[index]["raw_x"] is None
        ):
            index += 1

        gap_end = index - 1

        gap_length = (
            gap_end
            - gap_start
            + 1
        )

        previous_index = gap_start - 1
        next_index = index

        can_interpolate = (
            gap_length <= max_gap_frames
            and previous_index >= 0
            and next_index < len(records)
            and records[previous_index]["raw_x"]
            is not None
            and records[next_index]["raw_x"]
            is not None
        )

        if not can_interpolate:
            continue

        start_x = (
            records[previous_index]["raw_x"]
        )

        start_y = (
            records[previous_index]["raw_y"]
        )

        end_x = (
            records[next_index]["raw_x"]
        )

        end_y = (
            records[next_index]["raw_y"]
        )

        steps = gap_length + 1

        for step in range(
            1,
            gap_length + 1
        ):
            ratio = (
                step
                / steps
            )

            interpolated_x = (
                start_x
                + (end_x - start_x)
                * ratio
            )

            interpolated_y = (
                start_y
                + (end_y - start_y)
                * ratio
            )

            target_index = (
                previous_index
                + step
            )

            records[target_index]["raw_x"] = (
                interpolated_x
            )

            records[target_index]["raw_y"] = (
                interpolated_y
            )

            records[target_index]["status"] = (
                "interpolated"
            )

    return records


# =========================================================
# 12. 비정상 좌표 점프 제거
# =========================================================
def remove_large_jumps(
    records,
    max_jump
):
    previous_x = None
    previous_y = None

    for record in records:
        current_x = record["raw_x"]
        current_y = record["raw_y"]

        if (
            current_x is None
            or current_y is None
        ):
            continue

        if previous_x is None:
            previous_x = current_x
            previous_y = current_y
            continue

        jump_distance = distance(
            previous_x,
            previous_y,
            current_x,
            current_y
        )

        if jump_distance > max_jump:
            record["raw_x"] = previous_x
            record["raw_y"] = previous_y

            if record["status"] == "detected":
                record["status"] = (
                    "jump_filtered"
                )

            else:
                record["status"] += (
                    "+jump_filtered"
                )

        else:
            previous_x = current_x
            previous_y = current_y

    return records


# =========================================================
# 13. EMA 좌표 평활화
# =========================================================
def smooth_coordinates(
    records,
    alpha
):
    smooth_x = None
    smooth_y = None

    for record in records:
        current_x = record["raw_x"]
        current_y = record["raw_y"]

        if (
            current_x is None
            or current_y is None
        ):
            record["center_x"] = None
            record["center_y"] = None
            continue

        if smooth_x is None:
            smooth_x = current_x
            smooth_y = current_y

        else:
            smooth_x = (
                alpha * current_x
                + (1 - alpha)
                * smooth_x
            )

            smooth_y = (
                alpha * current_y
                + (1 - alpha)
                * smooth_y
            )

        record["center_x"] = smooth_x
        record["center_y"] = smooth_y

    return records


# =========================================================
# 14. Tracking 품질 판정
# =========================================================
def evaluate_tracking_quality(
    detection_rate,
    interpolation_ratio,
    missing_ratio
):
    good_condition = (
        detection_rate
        >= GOOD_DETECTION_RATE
        and missing_ratio
        <= GOOD_MISSING_RATIO
        and interpolation_ratio
        <= GOOD_INTERPOLATION_RATIO
    )

    if good_condition:
        return "GOOD"

    warning_condition = (
        detection_rate
        >= WARNING_DETECTION_RATE
        and missing_ratio
        <= WARNING_MISSING_RATIO
        and interpolation_ratio
        <= WARNING_INTERPOLATION_RATIO
    )

    if warning_condition:
        return "WARNING"

    return "LOW_QUALITY"


# =========================================================
# 15. 입력 영상 확인
# =========================================================
if not VIDEO_PATH.exists():
    raise FileNotFoundError(
        "영상 파일을 찾을 수 없습니다.\n"
        f"확인 경로: {VIDEO_PATH}"
    )

capture = cv2.VideoCapture(
    str(VIDEO_PATH)
)

if not capture.isOpened():
    raise ValueError(
        "영상 파일을 열 수 없습니다.\n"
        f"확인 경로: {VIDEO_PATH}"
    )

fps = capture.get(
    cv2.CAP_PROP_FPS
)

total_frames = int(
    capture.get(
        cv2.CAP_PROP_FRAME_COUNT
    )
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

capture.release()

if fps <= 0:
    raise ValueError(
        "영상 FPS 정보를 읽을 수 없습니다."
    )

if (
    frame_width <= 0
    or frame_height <= 0
):
    raise ValueError(
        "영상 해상도 정보를 읽을 수 없습니다."
    )


# =========================================================
# 16. 영상별 Tracking 기준 계산
# =========================================================
MAX_GAP_FRAMES = max(
    1,
    int(
        round(
            fps
            * MAX_GAP_SECONDS
        )
    )
)

frame_diagonal = math.sqrt(
    frame_width ** 2
    + frame_height ** 2
)

max_jump = (
    frame_diagonal
    * MAX_JUMP_RATIO
)


# =========================================================
# 17. 입력 정보 출력
# =========================================================
print()
print("=" * 50)

print(
    "PET TRACKING - REGISTERED SPECIES VERSION"
)

print("=" * 50)

print(
    f"Video        : {VIDEO_PATH.name}"
)

print(
    f"Video Path   : {VIDEO_PATH}"
)

print(
    f"Resolution   : "
    f"{frame_width} x {frame_height}"
)

print(
    f"FPS          : {fps:.3f}"
)

print(
    f"Total Frames : {total_frames}"
)

print(
    f"Registered   : {TARGET_CLASS_TEXT}"
)

print(
    f"Detection    : {DETECTION_CLASS_TEXT}"
)

print(
    f"YOLO Model   : {MODEL_PATH}"
)

print(
    f"Image Size   : {YOLO_IMAGE_SIZE}"
)

print(
    f"Confidence   : {YOLO_CONFIDENCE}"
)

print(
    f"Max Gap      : "
    f"{MAX_GAP_FRAMES} frames"
)

print(
    f"Max Gap Time : "
    f"{MAX_GAP_SECONDS:.2f} sec"
)

print(
    f"Max Jump     : "
    f"{max_jump:.2f} px"
)

print()


# =========================================================
# 18. YOLO + ByteTrack 실행
# =========================================================
model = YOLO(
    MODEL_PATH
)

results = model.track(
    source=str(VIDEO_PATH),
    stream=True,
    persist=True,

    # 등록 종이 있으면 해당 class만 사용하고,
    # 자동 모드에서만 cat과 dog class를 모두 사용한다.
    classes=DETECTION_CLASSES,

    tracker="bytetrack.yaml",

    imgsz=YOLO_IMAGE_SIZE,
    conf=YOLO_CONFIDENCE,
    iou=YOLO_IOU,

    verbose=False
)


# =========================================================
# 19. 프레임별 Tracking
# =========================================================
records = []

previous_x = None
previous_y = None

tracked_pet_type = (
    TARGET_PET_TYPE
)

tracked_class_id = (
    PET_CLASS_IDS.get(
        TARGET_PET_TYPE
    )
    if TARGET_PET_TYPE is not None
    else None
)

frame_number = 0


for result in results:
    frame_number += 1

    time_sec = (
        frame_number
        / fps
    )

    selected_x = None
    selected_y = None

    raw_track_id = None
    confidence = None

    pet_type = None
    class_id = None
    predicted_type = None
    predicted_class_id = None

    source_detected = False
    selected = None

    if (
        result.boxes is not None
        and len(result.boxes) > 0
    ):
        boxes = (
            result.boxes.xyxy
            .cpu()
            .numpy()
        )

        confidences = (
            result.boxes.conf
            .cpu()
            .numpy()
        )

        predicted_class_ids = (
            result.boxes.cls
            .int()
            .cpu()
            .tolist()
        )

        if result.boxes.id is not None:
            track_ids = (
                result.boxes.id
                .int()
                .cpu()
                .tolist()
            )

        else:
            track_ids = (
                [None]
                * len(boxes)
            )

        candidates = []

        for (
            box,
            candidate_confidence,
            candidate_track_id,
            detected_class_id
        ) in zip(
            boxes,
            confidences,
            track_ids,
            predicted_class_ids
        ):
            # YOLO classes 설정이 향후 변경되더라도
            # 등록 종과 다른 박스가 위치 후보로 사용되지
            # 않도록 후보 생성 단계에서도 한 번 더 검증한다.
            if (
                TARGET_PET_TYPE is not None
                and detected_class_id
                != PET_CLASS_IDS[TARGET_PET_TYPE]
            ):
                continue

            x1, y1, x2, y2 = box

            center_x = (
                x1 + x2
            ) / 2

            center_y = (
                y1 + y2
            ) / 2

            yolo_predicted_type = (
                PET_CLASS_NAMES.get(
                    detected_class_id,
                    "unknown"
                )
            )

            # 등록된 종이 있으면 등록 정보를 사용한다.
            if TARGET_PET_TYPE is not None:
                final_pet_type = (
                    TARGET_PET_TYPE
                )

                final_class_id = (
                    PET_CLASS_IDS[
                        TARGET_PET_TYPE
                    ]
                )

            # 등록된 종이 없으면 YOLO 예측을 사용한다.
            else:
                final_pet_type = (
                    yolo_predicted_type
                )

                final_class_id = (
                    detected_class_id
                )

            candidates.append({
                "x":
                    center_x,

                "y":
                    center_y,

                "track_id":
                    candidate_track_id,

                "confidence":
                    float(
                        candidate_confidence
                    ),

                "pet_type":
                    final_pet_type,

                "class_id":
                    final_class_id,

                "predicted_type":
                    yolo_predicted_type,

                "predicted_class_id":
                    detected_class_id
            })

        # -------------------------------------------------
        # 등록 종이 있는 경우:
        # YOLO와 후보 검증을 통과한 등록 종만 사용
        # -------------------------------------------------
        if TARGET_PET_TYPE is not None:
            valid_candidates = (
                candidates
            )

        # -------------------------------------------------
        # 등록 종이 없는 경우:
        # 첫 Detection 종을 고정한 후 동일 종만 사용
        # -------------------------------------------------
        else:
            if (
                tracked_pet_type is None
                and len(candidates) > 0
            ):
                first_candidate = max(
                    candidates,
                    key=lambda item:
                        item["confidence"]
                )

                tracked_pet_type = (
                    first_candidate[
                        "pet_type"
                    ]
                )

                tracked_class_id = (
                    first_candidate[
                        "class_id"
                    ]
                )

            valid_candidates = [
                candidate
                for candidate in candidates
                if candidate["pet_type"]
                == tracked_pet_type
            ]

        # -------------------------------------------------
        # 위치 후보 선택
        # -------------------------------------------------
        if len(valid_candidates) > 0:

            # 이전 위치가 있으면 가장 가까운 박스 선택
            if previous_x is not None:
                selected = min(
                    valid_candidates,

                    key=lambda item:
                        distance(
                            previous_x,
                            previous_y,
                            item["x"],
                            item["y"]
                        )
                )

            # 이전 위치가 없으면 confidence가 높은 박스 선택
            else:
                selected = max(
                    valid_candidates,

                    key=lambda item:
                        item["confidence"]
                )

        # -------------------------------------------------
        # 선택 결과 저장
        # -------------------------------------------------
        if selected is not None:
            selected_x = (
                selected["x"]
            )

            selected_y = (
                selected["y"]
            )

            raw_track_id = (
                selected["track_id"]
            )

            confidence = (
                selected["confidence"]
            )

            pet_type = (
                selected["pet_type"]
            )

            class_id = (
                selected["class_id"]
            )

            predicted_type = (
                selected["predicted_type"]
            )

            predicted_class_id = (
                selected[
                    "predicted_class_id"
                ]
            )

            source_detected = True

            previous_x = selected_x
            previous_y = selected_y

    records.append({
        "frame":
            frame_number,

        "time_sec":
            time_sec,

        "pet_id":
            1,

        "pet_type": (
            pet_type
            if pet_type is not None
            else tracked_pet_type
        ),

        "class_id": (
            class_id
            if class_id is not None
            else tracked_class_id
        ),

        "predicted_type":
            predicted_type,

        "predicted_class_id":
            predicted_class_id,

        "raw_track_id":
            raw_track_id,

        "confidence":
            confidence,

        "raw_x":
            selected_x,

        "raw_y":
            selected_y,

        "center_x":
            None,

        "center_y":
            None,

        "source_detected":
            source_detected,

        "status": (
            "detected"
            if source_detected
            else "missing"
        )
    })


# =========================================================
# 20. Tracking 후처리
# =========================================================
records = interpolate_short_gaps(
    records,
    MAX_GAP_FRAMES
)

records = remove_large_jumps(
    records,
    max_jump
)

records = smooth_coordinates(
    records,
    SMOOTHING_ALPHA
)


# =========================================================
# 21. Tracking 통계 계산
# =========================================================
raw_detected_count = sum(
    1
    for record in records
    if record["source_detected"]
)

interpolated_count = sum(
    1
    for record in records
    if "interpolated"
    in record["status"]
)

jump_filtered_count = sum(
    1
    for record in records
    if "jump_filtered"
    in record["status"]
)

missing_count = sum(
    1
    for record in records
    if record["center_x"] is None
)

track_ids = sorted({
    record["raw_track_id"]
    for record in records
    if record["raw_track_id"]
    is not None
})

detected_pet_types = [
    record["pet_type"]
    for record in records
    if (
        record["source_detected"]
        and record["pet_type"]
        is not None
    )
]

predicted_pet_types = [
    record["predicted_type"]
    for record in records
    if (
        record["source_detected"]
        and record["predicted_type"]
        is not None
    )
]


# 등록된 종이 있으면 등록 종을 최종값으로 사용
if TARGET_PET_TYPE is not None:
    detected_pet_type = (
        TARGET_PET_TYPE
    )

elif len(detected_pet_types) > 0:
    detected_pet_type = (
        Counter(
            detected_pet_types
        )
        .most_common(1)[0][0]
    )

else:
    detected_pet_type = "unknown"


# YOLO가 실제로 가장 많이 예측한 종
if len(predicted_pet_types) > 0:
    most_predicted_type = (
        Counter(
            predicted_pet_types
        )
        .most_common(1)[0][0]
    )

else:
    most_predicted_type = "unknown"


total_record_count = len(records)

if total_record_count > 0:
    detection_rate = (
        raw_detected_count
        / total_record_count
    )

    interpolation_ratio = (
        interpolated_count
        / total_record_count
    )

    missing_ratio = (
        missing_count
        / total_record_count
    )

else:
    detection_rate = 0.0
    interpolation_ratio = 0.0
    missing_ratio = 1.0


# =========================================================
# 22. Tracking 품질 판정
# =========================================================
tracking_quality = (
    evaluate_tracking_quality(
        detection_rate,
        interpolation_ratio,
        missing_ratio
    )
)

analysis_allowed = (
    tracking_quality
    != "LOW_QUALITY"
)


# =========================================================
# 23. 출력 폴더 생성
# =========================================================
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# 24. Tracking CSV 저장
# =========================================================
with open(
    TRACKING_OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:

    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "frame",
        "time_sec",
        "pet_id",
        "pet_type",
        "class_id",
        "predicted_type",
        "predicted_class_id",
        "raw_track_id",
        "confidence",
        "raw_x",
        "raw_y",
        "center_x",
        "center_y",
        "source_detected",
        "status"
    ])

    for record in records:
        writer.writerow([
            record["frame"],

            round(
                record["time_sec"],
                3
            ),

            record["pet_id"],

            (
                record["pet_type"]
                if record["pet_type"]
                is not None
                else ""
            ),

            (
                record["class_id"]
                if record["class_id"]
                is not None
                else ""
            ),

            (
                record["predicted_type"]
                if record["predicted_type"]
                is not None
                else ""
            ),

            (
                record["predicted_class_id"]
                if record["predicted_class_id"]
                is not None
                else ""
            ),

            (
                record["raw_track_id"]
                if record["raw_track_id"]
                is not None
                else ""
            ),

            (
                round(
                    record["confidence"],
                    4
                )
                if record["confidence"]
                is not None
                else ""
            ),

            (
                round(
                    record["raw_x"],
                    2
                )
                if record["raw_x"]
                is not None
                else ""
            ),

            (
                round(
                    record["raw_y"],
                    2
                )
                if record["raw_y"]
                is not None
                else ""
            ),

            (
                round(
                    record["center_x"],
                    2
                )
                if record["center_x"]
                is not None
                else ""
            ),

            (
                round(
                    record["center_y"],
                    2
                )
                if record["center_y"]
                is not None
                else ""
            ),

            record["source_detected"],
            record["status"]
        ])


# =========================================================
# 25. Tracking 품질 CSV 저장
# =========================================================
with open(
    QUALITY_OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:

    writer = csv.writer(
        csvfile
    )

    writer.writerow([
        "video",
        "registered_pet_type",
        "detected_pet_type",
        "most_predicted_type",
        "total_frames",
        "raw_detected_frames",
        "interpolated_frames",
        "missing_frames",
        "jump_filtered_frames",
        "detection_rate",
        "interpolation_ratio",
        "missing_ratio",
        "raw_track_id_count",
        "tracking_quality",
        "analysis_allowed"
    ])

    writer.writerow([
        VIDEO_PATH.name,

        (
            TARGET_PET_TYPE
            if TARGET_PET_TYPE is not None
            else ""
        ),

        detected_pet_type,
        most_predicted_type,
        total_record_count,
        raw_detected_count,
        interpolated_count,
        missing_count,
        jump_filtered_count,

        round(
            detection_rate,
            6
        ),

        round(
            interpolation_ratio,
            6
        ),

        round(
            missing_ratio,
            6
        ),

        len(track_ids),
        tracking_quality,
        analysis_allowed
    ])


# =========================================================
# 26. 결과 출력
# =========================================================
print()
print("=" * 50)

print(
    "PET TRACKING COMPLETE"
)

print("=" * 50)

print(
    f"Registered Pet     : "
    f"{TARGET_CLASS_TEXT}"
)

print(
    f"Detected Pet       : "
    f"{detected_pet_type}"
)

print(
    f"YOLO Main Predict  : "
    f"{most_predicted_type}"
)

print(
    f"Species Locked     : "
    f"{tracked_pet_type}"
)

print(
    f"Total Frames       : "
    f"{total_record_count}"
)

print(
    f"Raw Detected       : "
    f"{raw_detected_count}"
)

print(
    f"Interpolated       : "
    f"{interpolated_count}"
)

print(
    f"Jump Filtered      : "
    f"{jump_filtered_count}"
)

print(
    f"Remaining Missing  : "
    f"{missing_count}"
)

print(
    f"Raw Track IDs      : "
    f"{track_ids}"
)

print(
    "Logical Pet ID     : 1"
)

print()
print("-" * 50)

print(
    "TRACKING QUALITY"
)

print("-" * 50)

print(
    f"Detection Rate     : "
    f"{detection_rate * 100:.2f}%"
)

print(
    f"Interpolation Ratio: "
    f"{interpolation_ratio * 100:.2f}%"
)

print(
    f"Missing Ratio      : "
    f"{missing_ratio * 100:.2f}%"
)

print(
    f"Tracking Quality   : "
    f"{tracking_quality}"
)

print(
    f"Analysis Allowed   : "
    f"{analysis_allowed}"
)

print()
print("=" * 50)

print(
    "TRACKING OUTPUT"
)

print("=" * 50)

print(
    "Tracking CSV:"
)

print(
    TRACKING_OUTPUT_PATH
)

print()

print(
    "Quality CSV:"
)

print(
    QUALITY_OUTPUT_PATH
)
