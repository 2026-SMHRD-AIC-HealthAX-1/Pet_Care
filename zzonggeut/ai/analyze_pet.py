import cv2
import numpy as np
import pandas as pd
import pymysql
from ultralytics import YOLO

# ==========================================
# 0. 로컬 환경 설정 영역 (경로 및 DB 정보 수정 필요)
# ==========================================
VIDEO_PATH = './data/samF03.mp4'
OUTPUT_PATH = './data/output_samF03_roi.mp4'
CSV_PATH = './data/samF03_roi_visit_report.csv'

DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = '로컬DB비번입력'
DB_NAME = '실제DB명입력'
TARGET_PET_SEQ = 1  # PET_INFO 외래키(SEQ)

# 1. 모델 로드 (최초 실행 시 yolov8n.pt 자동 다운로드)
model = YOLO('yolov8n.pt')

cap = cv2.VideoCapture(VIDEO_PATH)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0: fps = 30.0
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))

# 3. ROI(밥그릇 위치) 좌표 설정 (영상 해상도 기준 비율)
roi = {
    "xmin": int(width * 0.5),
    "ymin": int(height * 0.4),
    "xmax": int(width * 0.9),
    "ymax": int(height * 0.9)
}

frame_count = 0
was_in_roi = False
approach_count = 0
visit_logs = []
current_visit_start_time = 0.0
current_visit_frames = 0

print(f"[{VIDEO_PATH}] ROI 상세 분석을 시작합니다...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    current_time_sec = frame_count / fps

    results = model(frame, verbose=False)
    boxes = results[0].boxes.xyxy.cpu().numpy()

    is_in_roi = False

    if len(boxes) > 0:
        x1, y1, x2, y2 = boxes[0][:4]
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        head_x = int(x2)
        head_y = int(cy)
        if roi["xmin"] <= head_x <= roi["xmax"] and roi["ymin"] <= head_y <= roi["ymax"]:
            is_in_roi = True

        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

    # 접근 횟수 및 체류 시간 계산 로직
    if is_in_roi and not was_in_roi:
        approach_count += 1
        current_visit_start_time = round(current_time_sec, 2)
        current_visit_frames = 1
    elif is_in_roi and was_in_roi:
        current_visit_frames += 1
    elif not is_in_roi and was_in_roi:
        duration_sec = round(current_visit_frames / fps, 2)
        visit_logs.append({
            "approach_index": approach_count,
            "approach_time_sec": current_visit_start_time,
            "stay_duration_sec": duration_sec
        })
        current_visit_frames = 0

    was_in_roi = is_in_roi

    box_color = (0, 255, 0) if is_in_roi else (255, 0, 0)
    cv2.rectangle(frame, (roi["xmin"], roi["ymin"]), (roi["xmax"], roi["ymax"]), box_color, 2)
    out.write(frame)

cap.release()
out.release()

if was_in_roi:
    duration_sec = round(current_visit_frames / fps, 2)
    visit_logs.append({
        "approach_index": approach_count,
        "approach_time_sec": current_visit_start_time,
        "stay_duration_sec": duration_sec
    })

# 4. DB(PET_ACT_RECORD) 직접 적재
try:
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, db=DB_NAME, charset='utf8mb4')
    cursor = conn.cursor()
    for log in visit_logs:
        sql = """
        INSERT INTO PET_ACT_RECORD (DTTM, PET_SEQ, ACT_NAME, ACT_TIME)
        VALUES (NOW(), %s, %s, %s);
        """
        cursor.execute(sql, (TARGET_PET_SEQ, "식사(ROI)", int(log["stay_duration_sec"])))
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ DB(PET_ACT_RECORD) 적재 완료!")
except Exception as e:
    print(f"⚠️ DB 적재 스킵/에러 (설정 확인 필요): {e}")

# 5. CSV 백업 리포트 저장
df_visits = pd.DataFrame(visit_logs)
df_visits.to_csv(CSV_PATH, index=False)

print(f"\n[분석 결과 요약]")
print(f"총 접근 횟수: {approach_count}회")
print(df_visits)
print(f"\n상세 리포트 CSV 저장 완료: {CSV_PATH}")