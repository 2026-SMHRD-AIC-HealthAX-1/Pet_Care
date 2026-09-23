import asyncio
import csv
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import shutil
import time
import uuid

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame
import cv2
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from pet_behavior_model.src.pet_behavior_analyzer import PetBehaviorAnalyzer
from pet_behavior_model.src.frame_sources import AnalysisContext
from pet_behavior_model.src.live_analyzer import LivePetBehaviorAnalyzer


# ==========================================
# 전역 설정
# ==========================================

CURRENT_MODE = "upload"

SPRING_MODE_NOTIFY_URL = "http://localhost:9090/api/ai/mode"
SPRING_ANALYSIS_RESULT_URL = "http://localhost:9090/api/pet/analysis"

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

active_tracks = {}
pcs = set()

analyzer = PetBehaviorAnalyzer()

KST = timezone(
    timedelta(hours=9)
)


# ==========================================
# Spring 통신
# ==========================================

async def notify_mode_to_spring(
    mode: str
):
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
                print(
                    f"[초기화 성공] "
                    f"Spring 서버에 모드 전송 완료: {mode}"
                )

            else:
                print(
                    f"[초기화 경고] "
                    f"Spring 응답 코드: "
                    f"{response.status_code}"
                )

        except Exception as e:
            print(
                f"[초기화 실패] "
                f"Spring 모드 전송 실패: {e}"
            )


async def send_result_to_spring(
    result: dict,
    mode=None
):
    payload = {
        "mode": mode or CURRENT_MODE,
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
                f"{response.status_code} / "
                f"{response.text}"
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
    species: str = "DOG",
    user_seq: str = None,
    roi_data: dict = None,
):
    if not os.path.exists(
        video_path
    ):
        raise FileNotFoundError(
            "대상 영상 파일이 존재하지 않습니다: "
            f"{video_path}"
        )

    unique_analysis_id = (
        f"ANL-{uuid.uuid4().hex[:8]}"
    )

    unique_video_id = (
        f"VID-{uuid.uuid4().hex[:8]}"
    )

    print(
        f"[분석 시작] {video_path}"
    )

    if roi_data:
        print(
            "[UPLOAD ROI 수신] "
            f"camera_id="
            f"{roi_data.get('camera_id')}, "
            f"roi_count="
            f"{len(roi_data.get('roi_areas', []))}"
        )

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
        roi_data=roi_data,
    )

    # Spring DB 저장용 로그인 사용자 식별값 유지
    if user_seq is not None:
        result["user_seq"] = user_seq

    result = attach_tracking_points(
        result,
        video_path,
    )

    print(
        "[분석 완료] "
        f"analysis_id="
        f"{unique_analysis_id}"
    )

    return result


def attach_tracking_points(
    result: dict,
    video_path: str,
):
    """
    PetBehaviorAnalyzer가 생성한 tracking CSV를 읽어
    대시보드 Canvas 표시용 tracking_points를 결과에 추가한다.
    기존 분석/ROI/LIVE 계약은 변경하지 않는다.
    """
    if not isinstance(result, dict):
        return result

    try:
        stem = Path(video_path).stem

        base_dir = Path(
            getattr(
                analyzer,
                "base_dir",
                BASE_DIR / "pet_behavior_model"
            )
        )

        tracking_csv_path = (
            base_dir
            / "data"
            / "outputs"
            / f"{stem}_tracking.csv"
        )

        tracking_points = []

        if tracking_csv_path.is_file():
            with tracking_csv_path.open(
                "r",
                encoding="utf-8",
                newline=""
            ) as csv_file:

                reader = csv.DictReader(
                    csv_file
                )

                for row in reader:
                    raw_x = (
                        row.get("raw_x")
                        or row.get("center_x")
                    )

                    raw_y = (
                        row.get("raw_y")
                        or row.get("center_y")
                    )

                    time_sec = (
                        row.get("time_sec")
                    )

                    if (
                        raw_x is None
                        or raw_y is None
                        or time_sec is None
                    ):
                        continue

                    raw_x = str(raw_x).strip()
                    raw_y = str(raw_y).strip()
                    time_sec = str(time_sec).strip()

                    if (
                        not raw_x
                        or not raw_y
                        or not time_sec
                    ):
                        continue

                    point = {
                        "time": float(time_sec),
                        "x": float(raw_x),
                        "y": float(raw_y),
                        "status": (
                            row.get("status")
                            or "detected"
                        ),
                    }

                    confidence = (
                        row.get("confidence")
                    )

                    if (
                        confidence is not None
                        and str(confidence).strip()
                    ):
                        try:
                            point["confidence"] = (
                                float(confidence)
                            )
                        except ValueError:
                            pass

                    tracking_points.append(
                        point
                    )

        result["tracking_points"] = (
            tracking_points
        )

        print(
            "[UPLOAD TRACKING] "
            f"tracking_csv="
            f"{tracking_csv_path}, "
            f"tracking_points="
            f"{len(tracking_points)}"
        )

    except Exception as e:
        result["tracking_points"] = []

        print(
            "[UPLOAD TRACKING 경고] "
            f"{type(e).__name__}: {e}"
        )

    return result


# ==========================================
# Lifespan
# ==========================================

@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    print(
        f"{datetime.now(KST)} : "
        f"AI 서버 시작 "
        f"(현재 모드: {CURRENT_MODE})"
    )

    await notify_mode_to_spring(
        CURRENT_MODE
    )

    yield

    coros = [
        pc.close()
        for pc in pcs
    ]

    if coros:
        await asyncio.gather(
            *coros
        )

    pcs.clear()

    print(
        f"{datetime.now(KST)} : "
        f"AI 서버 종료 완료"
    )


# ==========================================
# FastAPI App
# ==========================================

app = FastAPI(
    lifespan=lifespan
)

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
    pet_id: str = Form("PET-001"),
    camera_id: str = Form("CAM-001"),
    species: str = Form("DOG"),
    user_seq: str = Form(None),
    roi_data: str = Form(None),
):
    species = (
        species
        .strip()
        .upper()
    )

    if species not in {
        "DOG",
        "CAT"
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "species는 DOG 또는 "
                "CAT만 가능합니다."
            )
        )

    # ======================================
    # ROI JSON 문자열 → dict 변환
    # ======================================

    parsed_roi_data = None

    if roi_data:
        try:
            parsed_roi_data = (
                json.loads(
                    roi_data
                )
            )

            if not isinstance(
                parsed_roi_data,
                dict
            ):
                raise ValueError(
                    "roi_data root must be object"
                )

            roi_areas = (
                parsed_roi_data.get(
                    "roi_areas",
                    []
                )
            )

            if not isinstance(
                roi_areas,
                list
            ):
                raise ValueError(
                    "roi_areas must be list"
                )

            print(
                "[UPLOAD ROI 파싱 완료] "
                f"camera_id="
                f"{parsed_roi_data.get('camera_id')}, "
                f"roi_count="
                f"{len(roi_areas)}"
            )

        except (
            json.JSONDecodeError,
            ValueError
        ) as e:

            raise HTTPException(
                status_code=400,
                detail=(
                    "roi_data JSON 형식 오류: "
                    f"{e}"
                )
            )

    original_name = Path(
        video.filename
        or "uploaded_video.mp4"
    ).name

    suffix = Path(
        original_name
    ).suffix

    if not suffix:
        suffix = ".mp4"

    temp_name = (
        f"{uuid.uuid4().hex}"
        f"{suffix}"
    )

    temp_path = (
        UPLOAD_DIR
        / temp_name
    )

    try:

        print(
            "[업로드 수신] "
            f"{original_name}"
        )

        with temp_path.open(
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                video.file,
                buffer
            )

        print(
            "[임시 저장 완료] "
            f"{temp_path}"
        )

        result = await asyncio.to_thread(
            execute_video_analysis,
            str(temp_path),
            pet_id,
            camera_id,
            species,
            user_seq,
            parsed_roi_data,
        )

        await send_result_to_spring(
            result
        )

        return {
            "success": True,
            "message":
                "영상 분석 및 DB 저장 요청 완료",
            "analysis_id":
                result.get(
                    "analysis_id"
                ),
            "analysis_status":
                result.get(
                    "analysis_status"
                ),
            "data":
                result
        }

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:

        print(
            "[분석 실패] "
            f"{type(e).__name__}: "
            f"{e}"
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
                    "[임시파일 삭제 완료] "
                    f"{temp_path}"
                )

            except Exception as e:
                print(
                    "[임시파일 삭제 경고] "
                    f"{e}"
                )


# ==========================================
# WebRTC Track
# ==========================================

class CameraStreamTrack(
    VideoStreamTrack
):

    def __init__(
        self,
        camera_num=0,
        live_session=None,
        analysis_fps=3.0,
        video_path=None,
        user_seq=None,
    ):
        super().__init__()

        self.camera_num = (
            camera_num
        )

        self.video_path = (
            video_path
        )

        self.user_seq = (
            user_seq
        )

        self.source_type = (
            "video"
            if video_path
            else "camera"
        )

        if self.source_type == "video":
            self.cap = (
                cv2.VideoCapture(
                    video_path
                )
            )

        else:
            self.cap = (
                cv2.VideoCapture(
                    camera_num
                )
            )

        self.running = True

        self.live_session = (
            live_session
        )

        self.analysis_fps = (
            analysis_fps
        )

        self._analysis_period = (
            1.0
            / analysis_fps
        )

        self._analysis_started_at = (
            time.monotonic()
        )

        self._next_analysis_at = (
            self._analysis_started_at
        )

        self._analysis_index = 0

        self._analysis_queue = (
            asyncio.Queue(
                maxsize=30
            )
        )

        self._analysis_worker_task = (
            None
        )

        self._finished = False

        if not self.cap.isOpened():

            source = (
                video_path
                if video_path
                else camera_num
            )

            raise RuntimeError(
                "LIVE 영상 소스를 "
                f"열 수 없습니다: {source}"
            )

        print(
            "[LIVE SOURCE] "
            f"type={self.source_type}, "
            f"source="
            f"{self.video_path if self.video_path else self.camera_num}"
        )

        if (
            self.live_session
            is not None
        ):
            self._analysis_worker_task = (
                asyncio.create_task(
                    self._analysis_worker()
                )
            )


    async def _analysis_worker(
        self
    ):

        while True:

            item = await (
                self._analysis_queue.get()
            )

            if item is None:
                break

            frame, timestamp_sec = (
                item
            )

            try:

                emitted = (
                    await asyncio.to_thread(
                        self.live_session.push_frame,
                        frame,
                        timestamp_sec,
                    )
                )

                if emitted is not None:

                    print(
                        "[LIVE 5SEC] "
                        f"{emitted.get('start_sec')}"
                        f"~"
                        f"{emitted.get('end_sec')} sec"
                    )

            except Exception as e:

                print(
                    "[LIVE 분석 오류] "
                    f"{e}"
                )


    async def recv(
        self
    ):

        pts, time_base = (
            await self.next_timestamp()
        )

        ret, frame = (
            self.cap.read()
        )

        if not ret:

            if (
                self.source_type
                == "video"
            ):

                print(
                    "[LIVE VIDEO] "
                    "영상 끝 도달 "
                    "→ LIVE 분석 종료"
                )

                self.running = False

                await (
                    self.finish_live_analysis()
                )

                raise MediaStreamError

            else:

                raise RuntimeError(
                    "카메라 프레임을 "
                    "읽지 못했습니다."
                )

        # ------------------------------------------
        # AI 분석은 analysis_fps 기준으로 샘플링
        # WebRTC 영상은 원본 프레임 그대로 반환
        # ------------------------------------------

        if (
            self.live_session
            is not None
        ):

            now = (
                time.monotonic()
            )

            if (
                now
                >= self._next_analysis_at
            ):

                timestamp_sec = (
                    self._analysis_index
                    / self.analysis_fps
                )

                try:

                    self._analysis_queue.put_nowait(
                        (
                            frame.copy(),
                            timestamp_sec,
                        )
                    )

                    self._analysis_index += 1

                except asyncio.QueueFull:

                    print(
                        "[LIVE 경고] "
                        "분석 큐 한도 초과 "
                        f"- analysis_fps="
                        f"{self.analysis_fps} "
                        "처리 성능 재확인 필요"
                    )

                while (
                    self._next_analysis_at
                    <= now
                ):
                    self._next_analysis_at += (
                        self._analysis_period
                    )

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        video_frame = (
            VideoFrame.from_ndarray(
                rgb_frame,
                format="rgb24"
            )
        )

        video_frame.pts = pts
        video_frame.time_base = (
            time_base
        )

        return video_frame


    async def finish_live_analysis(
        self
    ):

        if self._finished:
            return None

        self._finished = True
        self.running = False

        if self.cap.isOpened():
            self.cap.release()

        if self.live_session is None:
            return None

        if (
            self._analysis_worker_task
            is not None
        ):

            await (
                self._analysis_queue.put(
                    None
                )
            )

            await (
                self._analysis_worker_task
            )

        try:

            result = (
                await asyncio.to_thread(
                    self.live_session.finish
                )
            )

            if self.user_seq is not None:
                result["user_seq"] = (
                    self.user_seq
                )

            print(
                "[LIVE 분석 완료] "
                f"analysis_id="
                f"{result.get('analysis_id')} "
                f"status="
                f"{result.get('analysis_status')}"
            )

            await send_result_to_spring(
                result,
                mode="live",
            )

            print(
                "[LIVE → Spring] "
                "결과 전송 완료"
            )

            return result

        except Exception as e:

            print(
                "[LIVE 종료 처리 오류] "
                f"{e}"
            )

            return None


    def release(
        self
    ):

        self.running = False

        if self.cap.isOpened():
            self.cap.release()


# ==========================================
# WebRTC Offer
# ==========================================

@app.post("/offer")
async def offer(
    request: Request
):

    params = (
        await request.json()
    )

    species = str(
        params.get(
            "species",
            "DOG"
        )
    ).strip().upper()

    if species not in (
        "DOG",
        "CAT"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "species는 DOG 또는 "
                "CAT만 가능합니다."
            )
        )

    pet_id = str(
        params.get(
            "pet_id",
            "PET-LIVE-TEST-001"
        )
    )

    camera_id = str(
        params.get(
            "camera_id",
            "CAM-001"
        )
    )

    user_seq = (
        str(
            params.get(
                "user_seq"
            )
        ).strip()
        if params.get(
            "user_seq"
        ) is not None
        else None
    )

    camera_num = int(
        params.get(
            "camera_num",
            0
        )
    )

    source_type = str(
        params.get(
            "source_type",
            "camera"
        )
    ).strip().lower()

    video_path = (
        params.get(
            "video_path"
        )
        or os.getenv(
            "LIVE_DEMO_VIDEO_PATH"
        )
    )

    if (
        source_type == "video"
        and not video_path
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "source_type=video 인 경우 "
                "video_path 또는 "
                "LIVE_DEMO_VIDEO_PATH "
                "환경변수가 필요합니다."
            )
        )

    roi_data = (
        params.get(
            "roi_data"
        )
    )

    # ROI가 비어 있으면 ROI 분석 미사용
    if (
        isinstance(
            roi_data,
            dict
        )
        and not roi_data.get(
            "roi_areas"
        )
    ):
        roi_data = None

    token = (
        uuid.uuid4()
        .hex[:10]
    )

    context = AnalysisContext(
        analysis_id=(
            f"ANL-LIVE-{token}"
        ),
        pet_id=pet_id,
        video_id=(
            f"VID-LIVE-{token}"
        ),
        camera_id=camera_id,
        species=species,
        recorded_at=(
            datetime.now(
                KST
            ).isoformat()
        ),
        roi_data=roi_data,
    )

    try:

        live_session = (
            LivePetBehaviorAnalyzer()
            .start_session(
                context=context,
                expected_fps=3.0,
            )
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=(
                "LIVE 분석 세션 생성 실패: "
                f"{e}"
            )
        )

    offer = RTCSessionDescription(
        sdp=params["sdp"],
        type=params["type"]
    )

    pc = RTCPeerConnection()

    pcs.add(
        pc
    )

    try:

        video_track = (
            CameraStreamTrack(
                camera_num=camera_num,
                live_session=live_session,
                analysis_fps=3.0,
                video_path=(
                    video_path
                    if source_type == "video"
                    else None
                ),
                user_seq=user_seq,
            )
        )

    except Exception as e:

        pcs.discard(
            pc
        )

        await pc.close()

        raise HTTPException(
            status_code=500,
            detail=(
                "카메라 Track 생성 실패: "
                f"{e}"
            )
        )

    pc.addTrack(
        video_track
    )

    active_tracks[pc] = (
        video_track
    )

    print(
        "[LIVE 세션 시작] "
        f"analysis_id="
        f"{context.analysis_id}, "
        f"pet_id="
        f"{pet_id}, "
        f"camera_id="
        f"{camera_id}, "
        f"species="
        f"{species}, "
        f"user_seq="
        f"{user_seq}, "
        f"analysis_fps=3, "
        f"source_type="
        f"{source_type}"
    )


    @pc.on(
        "connectionstatechange"
    )
    async def on_connectionstatechange():

        print(
            "[WebRTC 상태] "
            f"{pc.connectionState}"
        )

        if pc.connectionState in [
            "failed",
            "closed"
        ]:

            track = (
                active_tracks.pop(
                    pc,
                    None
                )
            )

            if track:
                await (
                    track.finish_live_analysis()
                )

            await pc.close()

            pcs.discard(
                pc
            )


    await pc.setRemoteDescription(
        offer
    )

    answer = (
        await pc.createAnswer()
    )

    await pc.setLocalDescription(
        answer
    )

    return {
        "sdp":
            pc.localDescription.sdp,

        "type":
            pc.localDescription.type,

        "analysis_id":
            context.analysis_id,

        "analysis_fps":
            3.0,
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