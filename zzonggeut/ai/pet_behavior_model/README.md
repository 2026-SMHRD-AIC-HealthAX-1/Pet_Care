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

공간 분석 코드는 별도로 존재하지만 현재 메인 파이프라인에는 연결되지 않아 결과 JSON에서 space_analysis는 null로 반환됩니다.

## 주요 구조

- src/model_api.py: FastAPI와 Spring 결과 전달
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

## Spring 전달 설정

기본 전달 주소:

http://localhost:8081/api/ai/analysis-results

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

- Python 소스 13개 문법 검사
- 분석 결과 JSON 11개 Schema 검사
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
- 공간 분석 메인 파이프라인 통합
