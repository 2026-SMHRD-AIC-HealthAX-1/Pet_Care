# Pet Behavior Model

반려동물 영상에서 행동 특징을 추출하고, 개체별 평소 패턴과 비교해 행동 변화를 감지한 뒤 통합 결과 JSON을 Spring으로 전달하는 모델 서버입니다.

## 핵심 기능

- YOLO 기반 DOG/CAT 객체 탐지 및 추적
- 5초 단위 행동 특징 산출
- 영상 전체 행동 특징 산출
- 개체·시간대별 7일 베이스라인 생성
- 평소 패턴 대비 변화 점수 및 주요 변화 요인 생성
- JSON Schema 기반 통합 결과 생성
- FastAPI 영상 분석 API
- Spring 결과 수신 API 자동 전달
- Spring 연결 실패 시 최대 3회 재시도

## 행동 특징

| 필드 | 설명 |
|---|---|
| activity_level | 이동 프레임을 기반으로 계산한 활동량 |
| stationary_ratio | 정지 상태로 판단된 프레임 비율 |
| normalized_travel_distance | 화면 크기로 정규화한 누적 이동 거리 |
| normalized_moving_speed | 화면 크기와 시간을 고려한 평균 이동 속도 |

기본 집계 단위는 5초입니다.

ROI가 입력되면 기존 Tracking CSV를 재사용해 공간 분석을 수행합니다. ROI가 없거나 빈 배열이면 결과 JSON의 `space_analysis`는 null입니다.

## 주요 구조

- src/model_api.py: FastAPI와 Spring 결과 전달
- src/pet_behavior_analyzer.py: 외부 Python 코드용 공식 호출 인터페이스
- src/run_pipeline.py: 전체 분석 파이프라인
- src/track_pet.py: 객체 탐지 및 추적
- src/extract_features.py: 행동 특징 산출
- src/detect_change.py: 베이스라인 비교 및 변화 감지
- src/generate_analysis_json.py: 통합 결과 JSON 생성
- schemas/analysis_result.schema.json: 결과 JSON 명세
- data/outputs/analysis_results: 최종 분석 결과
- data/inputs: 베이스라인 이력
- data/outputs/baselines: 생성된 베이스라인
- backup/model_api_before_spring.py: Spring 연동 전 백업

## 환경 준비

Windows PowerShell에서 프로젝트 폴더를 연 뒤 가상환경을 생성하고 라이브러리를 설치합니다.

가상환경 생성: python -m venv .venv

실행 정책 임시 설정: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

가상환경 활성화: .\.venv\Scripts\Activate.ps1

라이브러리 설치: pip install -r requirements.txt

기존 .venv가 정상적으로 존재하면 가상환경을 다시 생성할 필요가 없습니다.

## 모델 서버 실행

Spring 결과 수신 서버를 먼저 실행한 뒤 모델 서버를 실행합니다.

직접 실행: python src\model_api.py

Uvicorn 실행: python -m uvicorn src.model_api:app --host 0.0.0.0 --port 8000

모델 서버 주소: http://localhost:8000

상태 확인 주소: http://localhost:8000/health

정상 상태에서는 status가 UP이고 pipeline_ready가 true로 반환됩니다.

## Python 메소드 호출

`pet_behavior_model` 폴더를 현재 작업 디렉터리 또는 Python 경로에 둔 뒤 다음처럼 호출합니다.

```python
from src import PetBehaviorAnalyzer

analyzer = PetBehaviorAnalyzer()
result = analyzer.analyze(
    video_path="data/videos/sample.mp4",
    analysis_id="ANL-001",
    pet_id="PET-001",
    video_id="VID-001",
    camera_id="CAM-001",
    species="DOG",
    recorded_at="2026-09-16T10:00:00+09:00",
)
```

`analyze()`는 기존 `run_pipeline.py`를 실행하고 Schema 1.2 결과를 Python `dict`로 반환합니다. 분석 자체가 실패해도 Schema 1.2 `FAILED` 결과가 생성되면 해당 dict를 반환합니다. 결과 파일이 생성되지 않거나 읽기·Schema·식별정보 검증에 실패한 경우에는 `PetBehaviorAnalyzerError`의 하위 예외가 발생합니다. Spring 전송은 이 클래스가 수행하지 않습니다.

선택적 ROI는 `roi_data` dict로 전달합니다. `None` 또는 빈 `roi_areas`는 ROI 미입력으로 처리합니다.

Schema 1.2에서는 기존 ROI 집계값과 함께 접근 이벤트별 `visit_events`를 반환합니다. 정상 이탈은 `end_reason="EXIT"`, 영상 종료 시 ROI 내부에 남아 있는 이벤트는 `end_reason="VIDEO_END"`로 표현합니다.

## UPLOAD/LIVE 공통 입력 구조

- `FramePacket`: 디코딩된 BGR 프레임과 `timestamp_sec`
- `AnalysisContext`: 분석 ID, 반려동물, 카메라, 종, 촬영시각과 ROI
- `FrameSource`: timestamp가 있는 프레임 입력 공통 인터페이스
- `UploadFrameSource`: 기존 영상 파일을 `FramePacket`으로 읽는 구현

기존 `PetBehaviorAnalyzer.analyze()` UPLOAD 호출은 그대로 유지됩니다.

## LIVE Python 메소드 호출

백엔드는 분석별로 하나의 세션을 만들고 프레임을 순서대로 전달한 뒤 종료합니다.

```python
from src import AnalysisContext, LivePetBehaviorAnalyzer

live_analyzer = LivePetBehaviorAnalyzer()
session = live_analyzer.start_session(
    context=AnalysisContext(
        analysis_id="ANL-LIVE-001",
        pet_id="PET-001",
        video_id="VID-LIVE-001",
        camera_id="CAM-001",
        species="DOG",
        recorded_at="2026-09-17T15:00:00+09:00",
        roi_data={
            "camera_id": "CAM-001",
            "roi_areas": [
                {
                    "roi_id": "ROI-FOOD-001",
                    "roi_name": "FOOD_BOWL",
                    "roi_type": "RECTANGLE",
                    "x": 0.1,
                    "y": 0.6,
                    "width": 0.2,
                    "height": 0.2,
                }
            ],
        },
    ),
    expected_fps=10.0,
)

try:
    session.push_frame(frame_bgr, timestamp_sec=0.0)
    session.push_frame(next_frame_bgr, timestamp_sec=0.1)
    result = session.finish()
except Exception:
    session.abort()
    raise
```

`frame_bgr`는 OpenCV 형식의 3채널 BGR 배열입니다. timestamp는 세션 안에서
엄격하게 증가해야 하며 첫 timestamp를 기준으로 상대 시간이 유지됩니다. 빠진 시간 슬롯은
검은 프레임으로 기록하여 기존 Tracking이 탐지 누락으로 관찰하게 합니다. 해상도 변경,
빈 세션, 역순·중복 timestamp, 허용 범위를 넘는 긴 프레임 중단은 예외로 처리합니다.

`finish()`는 임시 LIVE 영상을 닫고 기존 `PetBehaviorAnalyzer.analyze()`를 호출합니다.
따라서 DOG/CAT Tracking, 5초 피처, ROI, 변화 감지, Schema 1.2 결과 생성은 기존 경로를
그대로 재사용하며 별도 YOLO/Tracking 구현을 만들지 않습니다. 임시 LIVE 영상은 성공과
실패 모두에서 제거됩니다.

현재 LIVE 연결은 프레임을 수신하면서 임시 영상으로 버퍼링하고 세션 종료 후 전체 분석을
실행하는 1차 구현입니다. 프레임마다 YOLO 결과나 5초 중간 결과를 즉시 반환하는 스트리밍
추론은 포함하지 않습니다.

## Spring 전달 설정

기본 전달 주소:

http://localhost:9090/api/ai/analysis-results

다른 Spring 서버를 사용할 경우 모델 서버 실행 전에 다음 환경변수를 설정합니다.

$env:SPRING_RESULT_URL = "http://서버주소:포트/api/ai/analysis-results"

## 분석 API

요청 주소: POST /api/v1/analyze

요청 형식: multipart/form-data

필수 필드:

- video: MP4, MOV, AVI 또는 MKV 영상
- analysis_id: 분석 고유 ID
- pet_id: 반려동물 고유 ID
- video_id: 영상 고유 ID
- camera_id: 카메라 고유 ID
- species: DOG 또는 CAT
- recorded_at: 타임존을 포함한 ISO 8601 촬영시각

선택 필드:

- recorded_at_source: 기본값 REQUEST_TIME
- time_slot: 1시간 단위 시간 구간

## 공식 Baseline 정책 v1

- 정책 버전: `baseline-policy-v1`
- 분리 기준: `pet_id + camera_id + time_slot + feature_version`
- 피처 버전: `pet-features-v2.0`
- 분석별 최소 완전 구간: 5초 구간 5개
- 최초 생성: 유효 날짜 대표값 7일
- 최초 후보: 완료 상태, GOOD/WARNING Tracking, `NOT_EVALUATED` 허용
- 갱신 후보: `NORMAL`, `SLIGHT_CHANGE`만 허용
- 갱신 제외: `STRONG_CHANGE`, `NOT_EVALUATED`
- 같은 날짜 내부: 완전 구간 수 기반 가중 평균
- Baseline 계산: 날짜 대표값을 날짜별 동일 가중치로 평균

신규 자동 파일 prefix:

`{pet_id}_{camera_id}_{time_slot}_{feature_version}_baseline-policy-v1`

공식 history는 `daily_samples` 배열에 날짜별 `analyses`와 `representative`를 저장합니다.
기존 Schema 1.0 history/Baseline과 정책 적용 전 Schema 1.1 history는 자동 이관하지 않습니다.

Baseline JSON과 CSV는 반드시 함께 존재해야 하며, JSON과 CSV의 다음 identity를 모두 검증합니다.

- `schema_version=1.1`
- `policy_version=baseline-policy-v1`
- `pet_id`
- `camera_id`
- `feature_version=pet-features-v2.0`
- `aggregation_sec=5.0`
- `time_slot`
- `reference_days=7`

직접 파이프라인을 실행하면서 Baseline 경로를 지정할 때는 CSV 위치 인자와 함께 필요하면
`--baseline-json`으로 메타데이터 JSON 경로를 지정합니다.

## 응답 헤더

- X-Analysis-Reused: 기존 결과 재사용 여부
- X-Spring-Delivery: delivered이면 Spring 전달 성공
- X-Pipeline-Return-Code: 신규 파이프라인 종료 코드

## 전달 실패 처리

Spring 전달에 실패하면 최대 3회 재시도합니다.

모든 시도가 실패하면 HTTP 502와 SPRING_DELIVERY_FAILED를 반환합니다.

전달 실패 시에도 생성된 분석 결과 JSON은 삭제하지 않습니다.

Spring 복구 후 동일한 analysis_id, pet_id, video_id, species로 다시 요청하면 기존 결과를 Spring으로 재전송합니다.

## 검증 완료 항목

- Python 소스 및 공개 호출 인터페이스 문법 검사
- Schema 1.0/1.1 보존 및 Schema 1.2 결과 검사
- ROI `visit_events` 단위·계약 검사
- 강아지·고양이 분석 결과 생성
- 강아지·고양이 기존 결과 Spring 전달
- 신규 강아지 분석 후 Spring 자동 전달
- Spring 중단 시 3회 재시도 및 HTTP 502 반환
- 전달 실패 후 결과 JSON 보존
- Spring 복구 후 기존 결과 재전송

## 현재 범위 밖

다음 항목은 실제 서비스 백엔드 개발 범위입니다.

- 분석 결과 DB 저장
- pet_id와 반려동물 테이블 연결
- 분석 결과 조회 API
- 프론트엔드 화면 연결
- 사용자 인증
- 알림 발송
- LIVE WebSocket/HTTP 전송 API와 세션 저장소
- 프레임별 즉시 Tracking 오버레이 및 5초 중간 결과 push
