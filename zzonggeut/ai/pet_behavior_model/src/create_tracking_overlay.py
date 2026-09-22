from ultralytics import YOLO
import cv2
import math
import sys
from pathlib import Path
from collections import deque

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "yolo11s.pt"

PET_CLASS_IDS = {
    "cat": 15,
    "dog": 16,
}

PET_CLASS_NAMES = {
    15: "cat",
    16: "dog",
}

YOLO_IMAGE_SIZE = 960
YOLO_CONFIDENCE = 0.15
YOLO_IOU = 0.50


def distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


if len(sys.argv) < 2:
    raise ValueError(
        "Usage: python src/create_tracking_overlay.py <video_path> [dog|cat]"
    )

video_path = Path(sys.argv[1]).resolve()

if not video_path.exists():
    raise FileNotFoundError(video_path)

target_pet_type = None

if len(sys.argv) >= 3:
    target_pet_type = sys.argv[2].strip().lower()

    if target_pet_type not in PET_CLASS_IDS:
        raise ValueError("species must be dog or cat")

if target_pet_type is not None:
    detection_classes = [PET_CLASS_IDS[target_pet_type]]
else:
    detection_classes = [15, 16]

output_path = (
    video_path.parent
    / f"{video_path.stem}_overlay.mp4"
)

capture = cv2.VideoCapture(str(video_path))

if not capture.isOpened():
    raise ValueError(f"Cannot open video: {video_path}")

fps = capture.get(cv2.CAP_PROP_FPS)
width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

capture.release()

if fps <= 0:
    fps = 30.0

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

writer = cv2.VideoWriter(
    str(output_path),
    fourcc,
    fps,
    (width, height),
)

if not writer.isOpened():
    raise ValueError(f"Cannot create output video: {output_path}")

model = YOLO(str(MODEL_PATH))

results = model.track(
    source=str(video_path),
    stream=True,
    persist=True,
    classes=detection_classes,
    tracker="bytetrack.yaml",
    imgsz=YOLO_IMAGE_SIZE,
    conf=YOLO_CONFIDENCE,
    iou=YOLO_IOU,
    verbose=False,
)

previous_x = None
previous_y = None
tracked_pet_type = target_pet_type

trail = deque(maxlen=max(1, int(fps * 3)))

frame_number = 0

for result in results:
    frame_number += 1

    frame = result.orig_img.copy()

    candidates = []

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.int().cpu().tolist()

        if result.boxes.id is not None:
            track_ids = result.boxes.id.int().cpu().tolist()
        else:
            track_ids = [None] * len(boxes)

        for box, conf, track_id, class_id in zip(
            boxes,
            confidences,
            track_ids,
            class_ids,
        ):
            if class_id not in PET_CLASS_NAMES:
                continue

            pet_type = PET_CLASS_NAMES[class_id]

            if (
                target_pet_type is not None
                and pet_type != target_pet_type
            ):
                continue

            x1, y1, x2, y2 = box

            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            candidates.append({
                "box": (
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2),
                ),
                "x": float(center_x),
                "y": float(center_y),
                "track_id": track_id,
                "confidence": float(conf),
                "pet_type": pet_type,
            })

    if tracked_pet_type is None and candidates:
        first_candidate = max(
            candidates,
            key=lambda item: item["confidence"],
        )

        tracked_pet_type = first_candidate["pet_type"]

    valid_candidates = [
        candidate
        for candidate in candidates
        if candidate["pet_type"] == tracked_pet_type
    ]

    selected = None

    if valid_candidates:
        if previous_x is not None:
            selected = min(
                valid_candidates,
                key=lambda item: distance(
                    previous_x,
                    previous_y,
                    item["x"],
                    item["y"],
                ),
            )
        else:
            selected = max(
                valid_candidates,
                key=lambda item: item["confidence"],
            )

    if selected is not None:
        x1, y1, x2, y2 = selected["box"]

        center = (
            int(selected["x"]),
            int(selected["y"]),
        )

        trail.append(center)

        if len(trail) >= 2:
            points = list(trail)

            for i in range(1, len(points)):
                cv2.line(
                    frame,
                    points[i - 1],
                    points[i],
                    (255, 185, 50),
                    3,
                    cv2.LINE_AA,
                )

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            3,
        )

        cv2.circle(
            frame,
            center,
            7,
            (0, 0, 255),
            -1,
        )

        track_text = (
            str(selected["track_id"])
            if selected["track_id"] is not None
            else "-"
        )

        label = (
            f"{selected['pet_type'].upper()} "
            f"ID:{track_text} "
            f"{selected['confidence']:.2f}"
        )

        cv2.putText(
            frame,
            label,
            (x1, max(30, y1 - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        previous_x = selected["x"]
        previous_y = selected["y"]

    else:
        trail.clear()

    cv2.putText(
        frame,
        f"TRACKING DEMO | Frame {frame_number}",
        (25, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    writer.write(frame)

writer.release()

print()
print("=" * 60)
print("TRACKING OVERLAY COMPLETE")
print("=" * 60)
print(f"Input : {video_path}")
print(f"Output: {output_path}")
print(f"Pet   : {tracked_pet_type}")
print("=" * 60)
