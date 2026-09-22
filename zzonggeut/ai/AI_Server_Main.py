import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import shutil
import uuid

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import cv2
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from pet_behavior_model.src.pet_behavior_analyzer import PetBehaviorAnalyzer


# ==========================================
# 전역 설정
# ==========================================

CURRENT_MODE = "upload"

SPRING_MODE_NOTIFY_URL = "http://localhost:9090/api/ai/mode"
SPRING_ANALYSIS_RESULT_URL = "http://localhost:9090/api/pet/analysis"

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

active_tracks = {}
pcs = set()

analyzer = PetBehaviorAnalyzer()

KST = timezone(timedelta(hours=9))


# ==========================================
# Spring 통신
# ==========================================

async def notify_mode_to_spring(mode: str):
    payload = {
        "mode": mode,
        "timestamp": datetime.now(KST).isoformat()
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                SPRING_MODE_NOTIFY_URL,
                json=payload,
                timeout=5.0
            )

            if response.status_code == 200:
                print(f"[초기화 성공] Spring 서버에 모드 전송 완료: {mode}")
            else:
                print(
                    f"[초기화 경고] Spring 응답 코드: "
                    f"{response.status_code}"
                )

        except Exception as e:
            print(f"[초기화 실패] Spring 모드 전송 실패: {e}")


async def send_result_to_spring(result: dict):
    payload = {
        "mode": CURRENT_MODE,
        "analyzedAt": datetime.now(KST).isoformat(),
        "data": result
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPRING_ANALYSIS_RESULT_URL,
            json=payload,
            timeout=30.0
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Spring 결과 전송 실패: "
                f"{response.status_code} / {response.text}"
            )

        print(
            f"[Spring 전송 완료] "
            f"Status: {response.status_code}"
        )


# ==========================================
# 실제 영상 분석
# ==========================================

def execute_video_analysis(
    video_path: str,
    pet_id: str = "PET-001",
    camera_id: str = "CAM-001",
    species: str = "DOG"
):
    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"대상 영상 파일이 존재하지 않습니다: {video_path}"
        )

    unique_analysis_id = f"ANL-{uuid.uuid4().hex[:8]}"
    unique_video_id = f"VID-{uuid.uuid4().hex[:8]}"

    print(f"[분석 시작] {video_path}")

    result = analyzer.analyze(
        video_path=video_path,
        analysis_id=unique_analysis_id,
        pet_id=pet_id,
        video_id=unique_video_id,
        camera_id=camera_id,
        species=species,
        recorded_at=datetime.now(KST).isoformat(),
        recorded_at_source="REQUEST_TIME",
        time_slot=None,
        roi_data=None,
    )

    print(
        f"[분석 완료] "
        f"analysis_id={unique_analysis_id}"
    )

    return result


# ==========================================
# Lifespan
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        f"{datetime.now(KST)} : "
        f"AI 서버 시작 (현재 모드: {CURRENT_MODE})"
    )

    await notify_mode_to_spring(CURRENT_MODE)

    yield

    coros = [pc.close() for pc in pcs]

    if coros:
        await asyncio.gather(*coros)

    pcs.clear()

    print(
        f"{datetime.now(KST)} : "
        f"AI 서버 종료 완료"
    )


# ==========================================
# FastAPI App
# ==========================================

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 상태 확인
# ==========================================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "mode": CURRENT_MODE,
        "service": "Pet Care AI Server"
    }


@app.get("/health")
async def health():
    return {
        "status": "UP",
        "mode": CURRENT_MODE
    }


# ==========================================
# 업로드 분석 API
# ==========================================

@app.post("/analyze-upload")
async def analyze_upload(
    video: UploadFile = File(...),
    pet_id: str = "PET-001",
    camera_id: str = "CAM-001",
    species: str = "DOG",
):
    species = species.upper()

    if species not in {"DOG", "CAT"}:
        raise HTTPException(
            status_code=400,
            detail="species는 DOG 또는 CAT만 가능합니다."
        )

    original_name = Path(
        video.filename or "uploaded_video.mp4"
    ).name

    suffix = Path(original_name).suffix

    if not suffix:
        suffix = ".mp4"

    temp_name = (
        f"{uuid.uuid4().hex}"
        f"{suffix}"
    )

    temp_path = UPLOAD_DIR / temp_name

    try:
        print(
            f"[업로드 수신] "
            f"{original_name}"
        )

        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(
                video.file,
                buffer
            )

        print(
            f"[임시 저장 완료] "
            f"{temp_path}"
        )

        result = await asyncio.to_thread(
            execute_video_analysis,
            str(temp_path),
            pet_id,
            camera_id,
            species
        )

        await send_result_to_spring(result)

        return {
            "success": True,
            "message": "영상 분석 및 DB 저장 요청 완료",
            "analysis_id": result.get("analysis_id"),
            "analysis_status": result.get("analysis_status"),
            "data": result
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except Exception as e:
        print(
            f"[분석 실패] "
            f"{type(e).__name__}: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        try:
            await video.close()
        except Exception:
            pass

        if temp_path.exists():
            try:
                temp_path.unlink()
                print(
                    f"[임시파일 삭제 완료] "
                    f"{temp_path}"
                )
            except Exception as e:
                print(
                    f"[임시파일 삭제 경고] "
                    f"{e}"
                )


# ==========================================
# WebRTC Track
# ==========================================

class CameraStreamTrack(VideoStreamTrack):

    def __init__(self, camera_num=0):
        super().__init__()

        self.camera_num = camera_num
        self.cap = cv2.VideoCapture(camera_num)
        self.running = True

        if not self.cap.isOpened():
            raise RuntimeError(
                f"카메라를 열 수 없습니다: "
                f"{camera_num}"
            )

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        ret, frame = self.cap.read()

        if not ret:
            raise RuntimeError(
                "카메라 프레임을 읽지 못했습니다."
            )

        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        video_frame = VideoFrame.from_ndarray(
            frame,
            format="rgb24"
        )

        video_frame.pts = pts
        video_frame.time_base = time_base

        return video_frame

    def release(self):
        self.running = False

        if self.cap.isOpened():
            self.cap.release()


# ==========================================
# WebRTC Offer
# ==========================================

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()

    offer = RTCSessionDescription(
        sdp=params["sdp"],
        type=params["type"]
    )

    pc = RTCPeerConnection()
    pcs.add(pc)

    video_track = CameraStreamTrack(
        params.get("camera_num", 0)
    )

    pc.addTrack(video_track)
    active_tracks[pc] = video_track

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():

        if pc.connectionState in [
            "failed",
            "closed"
        ]:
            track = active_tracks.pop(
                pc,
                None
            )

            if track:
                track.release()

            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()

    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }


# ==========================================
# Main
# ==========================================

if __name__ == "__main__":
    uvicorn.run(
        "AI_Server_Main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )