# LIVE Frame Pipeline Implementation Report

## 1. 확인된 기존 상태

- 기존 공식 호출 인터페이스는 `PetBehaviorAnalyzer.analyze(video_path=...)`입니다.
- 기존 분석은 영상 파일을 `run_pipeline.py`에 전달하는 UPLOAD 방식입니다.
- DOG/CAT Tracking, 5초 피처, ROI, 변화 감지, Schema 1.2 생성은 기존 파이프라인에 이미 연결되어 있습니다.
- 확인한 최신 소스에는 `FramePacket`, `AnalysisContext`, `FrameSource`, `UploadFrameSource`가 없었습니다.
- 기존 README도 LIVE 프레임 입력과 세션 관리를 범위 밖으로 명시하고 있었습니다.

## 2. 구현 방식

LIVE 입력을 위한 공통 데이터 구조와 세션 API를 추가했습니다.

1. 백엔드가 `AnalysisContext`로 분석 세션을 시작합니다.
2. `push_frame(frame, timestamp_sec)`으로 BGR 프레임을 순서대로 전달합니다.
3. LIVE 세션은 timestamp를 검사하고 임시 AVI에 프레임을 기록합니다.
4. timestamp에 빈 구간이 있으면 검은 프레임을 넣어 탐지 누락 구간으로 보존합니다.
5. `finish()`가 기존 `PetBehaviorAnalyzer.analyze()`를 호출합니다.
6. 기존 Tracking → 5초 피처 → ROI → 변화 감지 → Schema 1.2 생성을 그대로 재사용합니다.
7. 성공 또는 실패 후 LIVE 임시 영상만 자동 제거합니다.

객체 탐지와 Tracking을 새로 복제하지 않았으며 기존 Schema도 변경하지 않았습니다.

## 3. 수정·추가 파일

### 실제 소스 및 설정

- `src/frame_sources.py` 신규
- `src/live_analyzer.py` 신규
- `src/__init__.py` 공개 API export 추가
- `requirements.txt` 직접 사용하는 `numpy` 명시
- `README.md` LIVE 호출법과 제한사항 추가

### 테스트 코드

- `tests/test_live_analyzer.py` 신규

### 최종 검증 자료

- `LIVE_FRAME_PIPELINE_IMPLEMENTATION_REPORT.md` 신규

## 4. 공개 메소드

- `LivePetBehaviorAnalyzer.start_session(context=..., expected_fps=...)`
- `LiveAnalysisSession.push_frame(frame, timestamp_sec)`
- `LiveAnalysisSession.finish()`
- `LiveAnalysisSession.abort()`

## 5. UPLOAD와 LIVE 차이

| 구분 | UPLOAD | LIVE |
|---|---|---|
| 입력 | 완성된 영상 경로 | 순차 BGR 프레임 + timestamp |
| 시작 | `PetBehaviorAnalyzer.analyze()` | `start_session()` |
| 처리 시점 | 호출 즉시 전체 영상 분석 | `finish()` 후 전체 분석 |
| 분석 본체 | 기존 `run_pipeline.py` | 동일한 기존 `run_pipeline.py` |
| 최종 결과 | Schema 1.2 dict | Schema 1.2 dict |

## 6. 검증 결과

- Python 문법 검사: 통과
- 전체 단위 테스트: 42개 통과
- 기존 공개 인터페이스 회귀: 통과
- DOG/CAT 종 값 전달: 공통 `AnalysisContext`로 유지
- timestamp 증가·누락 슬롯 처리: 통과
- 해상도 변경 거부: 통과
- 빈 입력 거부: 통과
- 중도 종료 `abort()`: 통과
- 파이프라인 실패 시 임시 영상 제거: 통과
- 기존 ROI 및 Schema 1.1/1.2 테스트: 통과

실제 YOLO 가중치와 DOG/CAT 테스트 영상은 전달받은 작업용 소스 묶음에 포함되지 않아 실제 영상 전체 회귀는 이번 환경에서 실행하지 않았습니다.

## 7. 남은 제한사항

- 현재 1차 LIVE 구현은 프레임을 받으면서 임시 영상으로 버퍼링하고, 종료 후 전체 분석합니다.
- 프레임 수신과 동시에 YOLO Tracking 결과를 반환하는 실시간 추론은 아닙니다.
- 5초 단위 중간 결과 push, Tracking 오버레이 송출, WebSocket/HTTP 세션 API는 아직 없습니다.
- 세션 객체 저장, 만료, 재시작 및 여러 서버 간 공유는 백엔드 세션 관리 설계가 필요합니다.

## 8. 다음 권장 작업

Spring/AI 서버 사이 LIVE 전송 계약을 확정한 뒤 WebSocket 또는 프레임 업로드 API를 추가하고,
세션 ID 기준 시작·프레임 전달·종료·중단 엔드포인트를 연결합니다. 그 다음 실제 DOG/CAT 영상 프레임으로
UPLOAD 결과와 LIVE 종료 결과를 비교하는 회귀 테스트를 수행하는 것이 안전합니다.
