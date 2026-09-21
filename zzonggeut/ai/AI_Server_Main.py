import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import os
from pathlib import Path
from pprint import pprint
import threading
import time
import uuid

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import cv2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from datetime import datetime, timezone, timedelta

# AI 분석 모듈 임포트
from pet_behavior_model.src.pet_behavior_analyzer import PetBehaviorAnalyzer

# ==========================================
# 전역 설정e
# ==========================================
CURRENT_MODE = "upload"  # upload 모드로 고정

# Spring 서버 엔드포인트 설정
SPRING_BASE_URL = "http://localhost:8080"
SPRING_MODE_NOTIFY_URL = "http://localhost:9090/api/ai/mode"
SPRING_ANALYSIS_RESULT_URL = "http://localhost:9090/api/pet/analysis"

# 분석 대상 영상 디렉토리 또는 특정 파일 경로
# C:\Users\smhrd\Desktop\협력프로젝트\Corp_Project\pet_behavior_model
TARGET_VIDEO_PATH = os.getenv("TARGET_VIDEO_PATH", "C:/Users/smhrd/Desktop/협력프로젝트/Corp_Project/pet_behavior_model/example1.mp4")

# WebRTC 피어 관리
active_tracks = {}
pcs = set()

# AI 분석기 싱글톤 인스턴스
analyzer = PetBehaviorAnalyzer()

# 한국 표준시(KST, UTC+9) 타임존 객체 생성
KST = timezone(timedelta(hours=9))

# ==========================================
# Spring 통신 및 백그라운드 분석 루틴
# ==========================================
async def notify_mode_to_spring(mode: str):
    """서버 시작 시 Spring으로 현재 모드 전송"""
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "mode": mode,
                "timestamp": datetime.now().isoformat()
            }
            response = await client.post(SPRING_MODE_NOTIFY_URL, json=payload, timeout=5.0)
            if response.status_code == 200:
                print(f"[초기화 성공] Spring 서버에 모드 전송 완료: {mode}")
            else:
                print(f"[초기화 경고] Spring 응답 코드: {response.status_code}")
        except httpx.RequestError as e:
            print(f"[초기화 실패] Spring 서버 연결 불가: {e}")


def execute_video_analysis(video_path: str):
    """
    CPU/GPU 연산이 포함된 비디오 분석을 실행하는 동기 함수.
    asyncio.to_thread 내부에서 실행되어 이벤트 루프를 블로킹하지 않습니다.
    """
    if not os.path.exists(video_path):
        print(f"[경고] 대상 영상 파일이 존재하지 않습니다: {video_path}")
        return None

    unique_analysis_id = f"ANL-{uuid.uuid4().hex[:8]}"
    
    result = analyzer.analyze(
        video_path=video_path,
        analysis_id=unique_analysis_id,
        pet_id="PET-001",
        video_id="VID-001",
        camera_id="CAM-001",
        species="DOG",
        recorded_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        recorded_at_source="REQUEST_TIME",
        time_slot=None,
        roi_data=None,
    )
    return result


async def upload_analysis_loop():
    """10초 주기로 비디오를 분석하고 Spring 서버로 결과를 전송하는 백그라운드 루프"""
    print("[워커 시작] upload 모드 백그라운드 분석 워커 가동")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                print(f"[{datetime.now()}] 영상 분석 시작: {TARGET_VIDEO_PATH}")
                
                # 무거운 모델 연산을 별도 스레드에서 수행 (WebRTC 프레임 드랍 방지)
                result = await asyncio.to_thread(execute_video_analysis, TARGET_VIDEO_PATH)

                if result is not None:
                    payload = {
                        "mode": CURRENT_MODE,
                        "analyzedAt": datetime.now().isoformat(),
                        "data": result
                    }
                    
                    # Spring 서버로 분석 결과 전송
                    response = await client.post(
                        SPRING_ANALYSIS_RESULT_URL,
                        json=payload,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        print(f"[{datetime.now()}] Spring 전송 완료 (Status: {response.status_code})")
                    else:
                        print(f"[{datetime.now()}] Spring 전송 에러 (Status: {response.status_code})")
                        
            except httpx.RequestError as e:
                print(f"[{datetime.now()}] Spring 서버 통신 오류: {e}")
            except asyncio.CancelledError:
                print("[워커 종료] upload 모드 백그라운드 루프가 정상 종료되었습니다.")
                break
            except Exception as e:
                print(f"[{datetime.now()}] 비디오 분석 루프 예외 발생: {e}")

            # 10초 주기 대기 (상황에 맞게 초 조절 가능)
            await asyncio.sleep(10)


# ==========================================
# Lifespan 이벤트 핸들러
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [STARTUP]
    print(f"{datetime.now()} : AI 서버 시작 (현재 모드: {CURRENT_MODE})")

    # 1. Spring 서버로 모드 통보
    await notify_mode_to_spring(CURRENT_MODE)

    # 2. 10초 주기 업로드 분석 백그라운드 태스크 실행
    worker_task = asyncio.create_task(upload_analysis_loop())

    yield

    # [SHUTDOWN]
    # 백그라운드 루프 취소
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    # WebRTC 리소스 정리
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    print(f"{datetime.now()} : AI 서버 종료 완료")


# FastAPI 앱 생성
app = FastAPI(lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# WebRTC 관련 클래스 및 라우트 (기존 유지)
# ==========================================
class CameraStreamTrack(VideoStreamTrack):
    def __init__(self, camera_num):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_num, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.latest_frame = None
        self.running = True

        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame
            time.sleep(0.01)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        while self.latest_frame is None:
            await asyncio.sleep(0.01)

        frame = self.latest_frame
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

    def release(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()


@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    video_track = CameraStreamTrack(params.get("camera_num", 0))
    pc.addTrack(video_track)
    active_tracks[pc] = video_track

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ["failed", "closed"]:
            track = active_tracks.pop(pc, None)
            if track:
                track.release()
                print("카메라 리소스 반환 완료")
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }


if __name__ == "__main__":
    # reload=False 권장 (백그라운드 스레드 및 카메라 핸들 충돌 방지)
    uvicorn.run("AI_Server_Main:app", host="127.0.0.1", port=8000, reload=False)