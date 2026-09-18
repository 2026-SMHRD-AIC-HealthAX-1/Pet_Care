# LIVE 프레임 파이프라인 최종 구현 보고서

## 1. 최종 구현 목적

이번 작업의 목적은 기존 UPLOAD 분석 구조를 유지하면서,
반려동물 홈캠·웹캠 등에서 전달되는 LIVE 프레임을 실시간으로 분석할 수 있는 공통 AI 처리 구조를 완성하는 것입니다.

최종 목표는 다음과 같습니다.

- 기존 UPLOAD 분석 유지
- LIVE 프레임 입력 지원
- LIVE 중 YOLO 및 Tracking 수행
- 5초 단위 행동 피처 실시간 누적
- 완료된 5초 구간 중간 결과 조회
- ROI 공간분석 연동
- LIVE 종료 시 기존 분석 결과 재사용
- YOLO 및 Tracking 중복 실행 방지
- Baseline 및 변화 감지 연결
- Schema 1.2 최종 결과 생성
- AI 분석 결과를 Spring 9090으로 전달

---

## 2. 최종 지원 분석 방식

현재 AI 모델은 다음 두 가지 분석 방식을 모두 지원합니다.

### 2.1 UPLOAD

저장된 영상 파일을 대상으로 전체 분석을 수행합니다.

공개 호출 인터페이스:

```python
from src import PetBehaviorAnalyzer

analyzer = PetBehaviorAnalyzer()

result = analyzer.analyze(
    video_path="분석할 영상 경로",
    analysis_id="ANL-001",
    pet_id="PET-001",
    video_id="VID-001",
    camera_id="CAM-001",
    species="DOG",
    recorded_at="2026-09-18T10:00:00+09:00",
    recorded_at_source="REQUEST_TIME",
    time_slot=None,
    roi_data=None,
)
```

기존 UPLOAD 방식은 그대로 유지됩니다.

---

### 2.2 LIVE

LIVE 방식은 프레임을 순차적으로 전달받아 하나의 분석 세션을 유지하면서 처리합니다.

공개 호출 구조:

```python
from src import AnalysisContext, LivePetBehaviorAnalyzer

context = AnalysisContext(
    analysis_id="ANL-LIVE-001",
    pet_id="PET-001",
    video_id="VID-LIVE-001",
    camera_id="CAM-001",
    species="DOG",
    recorded_at="2026-09-18T10:00:00+09:00",
    recorded_at_source="REQUEST_TIME",
    time_slot=None,
    roi_data=None,
)

live_analyzer = LivePetBehaviorAnalyzer()

session = live_analyzer.start_session(
    context=context,
    expected_fps=5.0,
)

session.push_frame(frame_bgr, timestamp_sec=0.0)

intervals = session.poll_intervals()

result = session.finish()
```

---

## 3. LIVE 최종 처리 구조

최종 LIVE 분석 흐름은 다음과 같습니다.

```text
LIVE 프레임 수신
→ timestamp 검사
→ YOLO 객체 탐지
→ Tracking
→ Tracking 후처리
→ 이동량 및 행동 피처 계산
→ 5초 단위 피처 누적
→ 완료 구간 생성
→ poll_intervals()로 완료 구간 조회
→ ROI 상태 누적
→ finish()
→ analyze_precomputed()
→ 기존 계산 결과 재사용
→ ROI 최종 이벤트 확정
→ Baseline / 변화 감지
→ Schema 1.2 결과 생성
→ Spring 9090 결과 전달
```

LIVE 종료 시 전체 영상을 다시 처음부터 분석하지 않습니다.

세션 동안 이미 계산된 Tracking, 품질 정보, 행동 피처, 5초 구간 결과를 재사용하여
최종 분석 결과를 생성합니다.

---

## 4. LIVE 분석 FPS 기준

현재 MVP 기준 AI 분석 FPS는 **5 FPS**입니다.

이 값은 카메라 또는 웹 화면 자체가 5 FPS로 동작해야 한다는 의미가 아닙니다.

예를 들어 카메라가 30 FPS로 영상을 제공하는 경우:

```text
카메라 / 홈캠 영상
30 FPS
↓
AI용 프레임 샘플링
↓
AI 분석
5 FPS
```

즉 사용자는 일반적인 FPS의 영상을 볼 수 있고,
AI는 수신된 영상에서 필요한 프레임만 선택하여 약 5 FPS 기준으로 분석합니다.

실제 개발 PC에서 측정한 결과,
YOLO 및 Tracking 전체 처리 성능은 약 6~7 FPS 수준이었습니다.

따라서 현재 환경에서는 5 FPS가 실시간 처리를 안정적으로 유지할 수 있는 MVP 기준입니다.

5 FPS는 영구적인 고정값이 아니라 현재 하드웨어와 서비스 목적을 기준으로 정한 운영 기준입니다.

---

## 5. 5초 단위 분석

행동 피처는 다음 네 가지를 사용합니다.

- `activity_level`
- `stationary_ratio`
- `normalized_travel_distance`
- `normalized_moving_speed`

LIVE 세션에서는 프레임이 들어올 때마다 분석 데이터를 누적하고,
완전한 5초 구간이 만들어지면 해당 구간의 피처를 생성합니다.

`poll_intervals()`를 사용하면 세션 종료 전에도
새롭게 완료된 5초 단위 결과를 조회할 수 있습니다.

따라서 LIVE 분석은 단순히 프레임을 저장한 뒤 종료 후 분석하는 방식이 아닙니다.

---

## 6. LIVE 종료 처리

`finish()` 호출 시 다음 작업을 수행합니다.

1. 현재 LIVE 세션을 종료합니다.
2. 누적된 Tracking 결과를 정리합니다.
3. Tracking 품질 정보를 정리합니다.
4. 행동 피처 및 5초 구간 결과를 최종 확정합니다.
5. ROI 열린 접근 이벤트를 최종 처리합니다.
6. `PetBehaviorAnalyzer.analyze_precomputed()`를 호출합니다.
7. 이미 계산된 LIVE 결과를 기존 전체 파이프라인과 연결합니다.
8. Baseline 및 변화 감지를 수행합니다.
9. Schema 1.2 최종 결과를 생성합니다.

중요한 점은 `finish()` 시점에 YOLO 및 Tracking을 다시 실행하지 않는다는 것입니다.

---

## 7. ROI 공간분석 연동

LIVE 분석에서도 기존 ROI 공간분석 구조를 사용합니다.

ROI 좌표는 `0.0 ~ 1.0` 범위의 정규화 좌표를 사용합니다.

사각형 ROI 예시:

```json
{
  "camera_id": "CAM-001",
  "roi_areas": [
    {
      "roi_id": "ROI-BED-001",
      "roi_name": "BED",
      "roi_type": "RECTANGLE",
      "x": 0.2,
      "y": 0.2,
      "width": 0.4,
      "height": 0.4
    }
  ]
}
```

Tracking 결과의 중심 좌표를 기준으로 ROI 내부 진입 여부를 판단합니다.

ROI 접근 이벤트에는 다음 정보가 포함됩니다.

- 접근 순번
- 진입 시점
- 이탈 시점
- 개별 체류시간
- 종료 사유

종료 사유는 다음 두 가지입니다.

### EXIT

반려동물이 실제로 ROI 밖으로 이동한 경우입니다.

### VIDEO_END

반려동물이 ROI 안에 있는 상태에서 LIVE 분석이 종료된 경우입니다.

아직 진행 중인 접근 이벤트는 `finish()` 전에는 `VIDEO_END`로 확정하지 않습니다.

---

## 8. Baseline 및 변화 감지

현재 Baseline 정책은 다음과 같습니다.

- 피처 집계 단위: 5초
- Baseline history 반영 최소 완전 구간 수: 5개
- 기준 기간: 유효 날짜 7일
- 완전 구간 비율 기준: 90% 이상

Baseline이 아직 준비되지 않은 경우:

```text
baseline_status = NOT_READY
change_status = NOT_EVALUATED
```

이 상태는 오류가 아니라
평소 행동 기준을 만들기 위한 데이터가 아직 충분하지 않은 정상 상태입니다.

Baseline이 준비된 경우 변화 감지 결과는 다음 상태 중 하나로 반환됩니다.

- `NORMAL`
- `SLIGHT_CHANGE`
- `STRONG_CHANGE`

---

## 9. Schema 1.2

최종 결과는 Schema 1.2를 사용합니다.

현재 버전 정보:

```text
Schema Version: 1.2
Pipeline Version: pet-behavior-v1.1
Feature Version: pet-features-v2.0
```

Schema 1.2에서는 기존 분석 결과에 ROI 접근 이벤트별 결과인
`visit_events`가 포함됩니다.

Schema 1.1 결과와의 호환성도 기존 검증 범위에서 유지됩니다.

---

## 10. AI → Spring 결과 전달

AI 분석 완료 후 최종 Schema 1.2 결과를 Spring으로 전달합니다.

기본 Spring 수신 주소:

```text
POST http://localhost:9090/api/ai/analysis-results
Content-Type: application/json
```

실제 DOG 영상 분석 결과를 사용하여
AI 전체 분석 결과를 Spring으로 전송하는 End-to-End 테스트를 수행했습니다.

확인 결과:

- AI 분석 성공
- Schema 1.2 결과 생성
- Spring POST 전송 성공
- HTTP 200 응답
- 동일한 `analysis_id` 반환 확인

따라서 현재 AI → Spring 결과 전달 경로는 정상 동작합니다.

---

## 11. 실패 처리

Tracking 데이터가 충분하지 않은 경우
정상 결과를 억지로 생성하지 않고 실패 결과를 반환합니다.

실제 부족 영상 테스트 결과:

```text
analysis_status = FAILED
error.code = INSUFFICIENT_TRACKING
baseline_status = NOT_READY
change_status = NOT_EVALUATED
```

Tracking 부족 상황에서도
변화 감지 결과를 정상으로 오인하지 않도록 처리되어 있습니다.

Spring 결과 전달 실패 시에는 기존 모델 API 정책에 따라 재시도를 수행하며,
실패한 분석 결과 JSON은 보존됩니다.

---

## 12. 최종 검증 결과

### 단위 테스트

```text
45 tests
45 PASS
```

### UPLOAD 실영상

- DOG: PASS
- CAT: PASS

### LIVE 실영상

- DOG 5 FPS: PASS
- CAT 5 FPS: PASS

### LIVE 실시간성

- DOG 5 FPS: 실시간 처리 가능 확인
- CAT 5 FPS: 실시간 처리 가능 확인

### ROI

- ROI 접근 감지: PASS
- `EXIT`: PASS
- `VIDEO_END`: PASS
- 접근 이벤트 2회 이상 처리: PASS
- 세션 종료 전 잘못된 `VIDEO_END` 생성 방지: PASS

### Baseline / 변화 감지

- Baseline 미준비 상태: PASS
- `NOT_READY`: PASS
- `NOT_EVALUATED`: PASS
- Baseline 정책 코드 확인: PASS

### 실패 처리

- `INSUFFICIENT_TRACKING`: PASS
- 실패 Schema 1.2 결과: PASS

### Spring 연동

- Spring 9090 실행: PASS
- AI 결과 POST: PASS
- HTTP 200: PASS
- `analysis_id` 일치: PASS

---

## 13. 최종 수정 및 추가 파일

이번 최종 LIVE 통합 작업의 주요 변경 파일은 다음과 같습니다.

### AI

- `src/__init__.py`
- `src/live_analyzer.py`
- `src/live_processing.py`
- `src/pet_behavior_analyzer.py`
- `src/roi_space_analyzer.py`
- `src/run_pipeline.py`
- `tests/test_live_analyzer.py`
- `tests/run_live_local_regression.py`
- `README.md`

### Spring

- `AiAnalysisResultController.java`

---

## 14. 현재 완료 범위

현재 AI 모델 기준 완료된 범위는 다음과 같습니다.

- UPLOAD 분석
- LIVE 프레임 분석
- DOG/CAT Tracking
- 5초 행동 피처
- LIVE 중간 구간 조회
- ROI 공간분석
- ROI 접근 이벤트
- Baseline 연결
- 변화 감지
- Schema 1.2 결과 생성
- 실패 처리
- AI → Spring 결과 전송

---

## 15. 현재 범위 밖

다음 항목은 AI 모델 자체의 핵심 분석 기능이 아니라
서비스 백엔드 및 프론트엔드 연결 단계에 해당합니다.

- 분석 결과 DB 저장
- 반려동물 테이블과 `pet_id` 연결
- 분석 결과 조회 API
- LIVE WebSocket 또는 HTTP 프레임 수신 API
- LIVE 세션 저장소 및 세션 만료 관리
- 다중 서버 간 LIVE 세션 공유
- 실시간 Tracking 오버레이 화면 송출
- 프론트엔드 LIVE 화면 연결
- 사용자 인증
- 알림 발송

따라서 위 항목은 AI 모델 미완성 항목이 아니라
서비스 통합 단계에서 추가 구현해야 하는 범위입니다.

---

## 16. 최종 상태

현재 AI 모델은 다음 구조까지 완료되었습니다.

```text
UPLOAD / LIVE 입력
→ DOG/CAT 객체 탐지 및 Tracking
→ 5초 행동 피처
→ ROI 공간분석
→ Baseline
→ 행동 변화 감지
→ Schema 1.2
→ Spring 결과 전달
```

현재 단계에서는 AI 모델 핵심 분석 파이프라인을
최종 통합 버전으로 사용할 수 있는 상태입니다.

이후 주요 작업은 AI 내부 기능 추가가 아니라
Spring DB 저장, LIVE 전송 API, 프론트엔드 화면 연결 등
서비스 통합 작업입니다.