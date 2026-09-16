from fastapi import FastAPI
from datetime import datetime

# FastAPI 앱 생성
app = FastAPI()

# 스프링이 5초마다 요청을 보낼 주소 (GET /api/coordinate)
@app.get("/api/coordinate")
def get_pet_coordinate():
    # 나중에는 여기에 세인 님이 만든 YOLO 모델 코드를 연결해서 
    # 진짜 화면에서 감지된 x, y 좌표를 가져오면 됩니다!
    
    # 지금은 테스트용 가짜 좌표 리턴
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "cameraId": 1,
        "petId": 101,
        "x": 130,
        "y": 245,
        "timestamp": current_time
    }