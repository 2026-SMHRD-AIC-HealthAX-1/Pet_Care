import asyncio
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse


# =========================================================
# 1. 프로젝트 경로
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"

PIPELINE_SCRIPT = SRC_DIR / "run_pipeline.py"

UPLOAD_DIR = (
    BASE_DIR
    / "data"
    / "inputs"
    / "api_uploads"
)

RESULT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
    / "analysis_results"
)

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
}

IDENTIFIER_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
)

# 현재 파이프라인은 영상별 중간 결과 파일을 생성하므로
# MVP에서는 분석 요청을 한 번에 하나씩 처리한다.
ANALYSIS_LOCK = asyncio.Lock()

SPRING_RESULT_URL = os.getenv(
    "SPRING_RESULT_URL",
    "http://localhost:8081/api/ai/analysis-results",
)
SPRING_TIMEOUT_SEC = 10
SPRING_MAX_ATTEMPTS = 3


# =========================================================
# 2. FastAPI 앱
# =========================================================
app = FastAPI(
    title="Pet Behavior Analysis API",
    description=(
        "반려동물 영상을 분석하고 "
        "통합 분석 결과 JSON을 반환하는 모델 API"
    ),
    version="1.1.0",
)


# =========================================================
# 3. 공통 함수
# =========================================================
def validate_identifier(value: str, field_name: str) -> str:
    normalized = str(value).strip()

    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REQUEST",
                "message": (
                    f"{field_name}은 영문 또는 숫자로 시작하고, "
                    "영문·숫자·점(.)·밑줄(_)·하이픈(-)만 사용할 수 있으며 "
                    "128자 이하여야 합니다."
                ),
            },
        )

    return normalized


def validate_species(value: str) -> str:
    normalized = str(value).strip().lower()

    if normalized not in {"cat", "dog"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REQUEST",
                "message": "species는 CAT 또는 DOG만 허용합니다.",
            },
        )

    return normalized


def validate_video_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_VIDEO_FORMAT",
                "message": (
                    "지원하지 않는 영상 형식입니다. "
                    "허용 형식: .mp4, .mov, .avi, .mkv"
                ),
            },
        )

    return extension


def load_result_json(result_path: Path) -> dict:
    try:
        with result_path.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INVALID_RESULT_JSON",
                "message": (
                    "모델이 생성한 결과 JSON을 읽을 수 없습니다. "
                    f"{error}"
                ),
            },
        ) from error

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RESULT_READ_ERROR",
                "message": (
                    "모델 결과 파일을 읽는 중 오류가 발생했습니다. "
                    f"{error}"
                ),
            },
        ) from error


def post_result_to_spring(result: dict) -> dict:
    request_body = json.dumps(
        result,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        SPRING_RESULT_URL,
        data=request_body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=SPRING_TIMEOUT_SEC,
        ) as response:
            response_text = response.read().decode("utf-8")

    except urllib.error.HTTPError as error:
        response_text = error.read().decode(
            "utf-8",
            errors="replace",
        )
        raise RuntimeError(
            "Spring 결과 수신 API가 오류를 반환했습니다. "
            f"status={error.code}, body={response_text[:1000]}"
        ) from error

    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise RuntimeError(
            "Spring 결과 수신 API에 연결할 수 없습니다. "
            f"url={SPRING_RESULT_URL}, error={error}"
        ) from error

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Spring 응답이 올바른 JSON이 아닙니다. "
            f"body={response_text[:1000]}"
        ) from error

    if response_json.get("success") is not True:
        raise RuntimeError(
            "Spring이 분석 결과 수신 성공을 확인하지 않았습니다. "
            f"response={response_json}"
        )

    if response_json.get("analysis_id") != result.get("analysis_id"):
        raise RuntimeError(
            "Spring 응답의 analysis_id가 전송한 결과와 다릅니다. "
            f"sent={result.get('analysis_id')!r}, "
            f"received={response_json.get('analysis_id')!r}"
        )

    return response_json


async def deliver_result_to_spring(result: dict) -> dict:
    last_error = None

    for attempt in range(1, SPRING_MAX_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(
                post_result_to_spring,
                result,
            )
        except RuntimeError as error:
            last_error = error

            if attempt < SPRING_MAX_ATTEMPTS:
                await asyncio.sleep(attempt)

    raise HTTPException(
        status_code=502,
        detail={
            "code": "SPRING_DELIVERY_FAILED",
            "message": (
                "분석 결과는 생성·보존되었지만 Spring 전달에 실패했습니다. "
                "동일 analysis_id로 다시 요청하면 기존 결과를 재전송합니다."
            ),
            "spring_url": SPRING_RESULT_URL,
            "attempts": SPRING_MAX_ATTEMPTS,
            "error": str(last_error),
        },
    )

def check_existing_result(
    result_path: Path,
    analysis_id: str,
    pet_id: str,
    video_id: str,
    camera_id: str,
    species: str,
) -> Optional[dict]:
    if not result_path.exists():
        return None

    existing = load_result_json(result_path)

    expected = {
        "analysis_id": analysis_id,
        "pet_id": pet_id,
        "video_id": video_id,
        "camera_id": camera_id,
        "species": species.upper(),
    }

    mismatches = []

    for field_name, expected_value in expected.items():
        existing_value = existing.get(field_name)

        if existing_value != expected_value:
            mismatches.append(
                f"{field_name}: "
                f"기존={existing_value!r}, 요청={expected_value!r}"
            )

    if mismatches:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ANALYSIS_ID_CONFLICT",
                "message": (
                    "동일 analysis_id가 다른 분석 요청에 "
                    "이미 사용되었습니다."
                ),
                "details": mismatches,
            },
        )

    return existing


async def save_uploaded_video(
    video: UploadFile,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with destination.open("wb") as output_file:
            while chunk := await video.read(1024 * 1024):
                output_file.write(chunk)

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "VIDEO_SAVE_ERROR",
                "message": (
                    "업로드 영상을 저장하는 중 오류가 발생했습니다. "
                    f"{error}"
                ),
            },
        ) from error

    finally:
        await video.close()

    if not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REQUEST",
                "message": "업로드된 영상 파일이 비어 있습니다.",
            },
        )


# =========================================================
# 4. 상태 확인 API
# =========================================================
@app.get("/health")
async def health_check():
    return {
        "status": "UP",
        "service": "pet-behavior-model-api",
        "version": "1.1.0",
        "pipeline_ready": PIPELINE_SCRIPT.is_file(),
    }


# =========================================================
# 5. 영상 분석 API
# =========================================================
@app.post("/api/v1/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    analysis_id: str = Form(...),
    pet_id: str = Form(...),
    video_id: str = Form(...),
    camera_id: str = Form(...),
    species: str = Form(...),
    recorded_at: str = Form(...),
    recorded_at_source: str = Form("REQUEST_TIME"),
    time_slot: Optional[str] = Form(None),
):
    if not PIPELINE_SCRIPT.is_file():
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PIPELINE_NOT_FOUND",
                "message": (
                    "run_pipeline.py를 찾을 수 없습니다. "
                    f"확인 경로: {PIPELINE_SCRIPT}"
                ),
            },
        )

    analysis_id = validate_identifier(
        analysis_id,
        "analysis_id",
    )
    pet_id = validate_identifier(
        pet_id,
        "pet_id",
    )
    video_id = validate_identifier(
        video_id,
        "video_id",
    )
    camera_id = validate_identifier(
        camera_id,
        "camera_id",
    )
    species = validate_species(species)

    original_filename = video.filename or "uploaded_video"
    extension = validate_video_extension(original_filename)

    result_path = (
        RESULT_DIR
        / f"{analysis_id}_result.json"
    )

    # 동일 요청이 이미 완료됐다면 기존 결과를 반환한다.
    existing_result = check_existing_result(
        result_path=result_path,
        analysis_id=analysis_id,
        pet_id=pet_id,
        video_id=video_id,
        camera_id=camera_id,
        species=species,
    )

    if existing_result is not None:
        await deliver_result_to_spring(existing_result)

        return JSONResponse(
            status_code=200,
            content=existing_result,
            headers={
                "X-Analysis-Reused": "true",
                "X-Spring-Delivery": "delivered",
            },
        )

    # 중간 CSV 파일명이 영상명으로 생성되므로
    # analysis_id를 사용해 요청별 영상명을 고유하게 만든다.
    upload_path = (
        UPLOAD_DIR
        / f"{analysis_id}{extension}"
    )

    await save_uploaded_video(
        video,
        upload_path,
    )

    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        str(upload_path),
        species,
        "--analysis-id",
        analysis_id,
        "--pet-id",
        pet_id,
        "--video-id",
        video_id,
        "--camera-id",
        camera_id,
        "--recorded-at",
        recorded_at,
        "--recorded-at-source",
        recorded_at_source.strip().upper(),
    ]

    if time_slot and time_slot.strip():
        command.extend([
            "--time-slot",
            time_slot.strip(),
        ])

    try:
        async with ANALYSIS_LOCK:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(BASE_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            output_bytes, _ = await process.communicate()

        pipeline_output = output_bytes.decode(
            "utf-8",
            errors="replace",
        )

        # 실패 분석도 run_pipeline.py에서 FAILED 결과 JSON을 생성하므로
        # 결과 파일이 있으면 정상적인 분석 응답으로 반환한다.
        if result_path.is_file():
            result = load_result_json(result_path)

            expected_identity = {
                "analysis_id": analysis_id,
                "pet_id": pet_id,
                "video_id": video_id,
                "camera_id": camera_id,
                "species": species.upper(),
            }

            for field_name, expected_value in expected_identity.items():
                if result.get(field_name) != expected_value:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "code": "RESULT_IDENTITY_MISMATCH",
                            "message": (
                                "생성된 분석 결과의 식별정보가 "
                                "요청 정보와 일치하지 않습니다."
                            ),
                            "field": field_name,
                        },
                    )

            await deliver_result_to_spring(result)

            return JSONResponse(
                status_code=200,
                content=result,
                headers={
                    "X-Pipeline-Return-Code": str(
                        process.returncode
                    ),
                    "X-Analysis-Reused": "false",
                    "X-Spring-Delivery": "delivered",
                },
            )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "ANALYSIS_RESULT_NOT_CREATED",
                "message": (
                    "파이프라인 실행 후 결과 JSON이 "
                    "생성되지 않았습니다."
                ),
                "pipeline_return_code": process.returncode,
                "pipeline_output": pipeline_output[-4000:],
            },
        )

    finally:
        # 분석에 사용한 임시 업로드 영상만 제거한다.
        # 분석 결과 JSON과 CSV 파일은 유지한다.
        upload_path.unlink(missing_ok=True)


# =========================================================
# 6. 직접 실행
# =========================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
