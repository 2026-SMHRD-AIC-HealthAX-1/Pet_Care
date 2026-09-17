# ROI visit_events / Schema 1.2 구현 보고서

## 구현 결과

- 기존 Tracking CSV의 `frame`, `time_sec`, `center_x`, `center_y`, `source_detected`, `status`만 재사용합니다.
- ROI 분석 과정에서 YOLO 또는 Tracking을 다시 실행하지 않습니다.
- 기존 ROI 집계 필드와 함께 `visit_events`를 반환합니다.
- 정상 이탈은 `EXIT`, 영상 종료까지 체류한 이벤트는 `VIDEO_END`로 반환합니다.
- 좌표가 없는 Tracking 구간은 체류시간을 누적하지 않으며, 기존 안/밖 상태를 유지하여 거짓 재접근을 만들지 않습니다.
- `minimum_stay_sec` 미만 이벤트는 집계와 `visit_events` 양쪽에서 제외합니다.

## 버전

- `schema_version`: `1.2`
- `pipeline_version`: `pet-behavior-v1.2`
- `calculation_version`: `roi-space-v2`
- `feature_version`: `pet-features-v2.0` 유지

Schema 1.0과 기존 Schema 1.1(`analysis_result.schema.json`)은 수정하지 않았습니다. 이름이 명시된 보존본 `analysis_result_v1.1.schema.json`과 신규 `analysis_result_v1.2.schema.json`을 추가했습니다.

## visit_events 예시

```json
{
  "event_index": 1,
  "entry_time_sec": 10.2,
  "exit_time_sec": 18.7,
  "stay_time_sec": 8.5,
  "end_reason": "EXIT"
}
```

영상 종료까지 ROI 내부인 경우:

```json
{
  "event_index": 2,
  "entry_time_sec": 25.0,
  "exit_time_sec": null,
  "stay_time_sec": 6.25,
  "end_reason": "VIDEO_END"
}
```

## 보호 대상 SHA256 비교

| 보호 대상 | 변경 전 | 변경 후 | 결과 |
|---|---|---|---|
| `src/track_pet.py` | `086e901a43971eecdc0107082ae44b968912e5af9349e03327d94ef23c3666a7` | 동일 | 보호됨 |
| `src/extract_features.py` | `a87fc676c543478ff975542b3246d5b9939ffe82d4d186dc2be4f7ad91f66bfe` | 동일 | 보호됨 |
| `src/detect_change.py` | `79529d21946f5ea2c84256e4f76dafa209fcac0e244fed82b6c87e7144fc8d54` | 동일 | 보호됨 |
| `src/baseline_policy.py` | `92af92e42a13b6ecb44573d6e9880b9f4c2606199eb65d7892833a8371d4b7ff` | 동일 | 보호됨 |
| `schemas/analysis_result_v1.0.schema.json` | `89ea657ff33016d85ae54cba606a0deb54da50968c24e4599faa4d50343e56c3` | 동일 | 보호됨 |
| 기존 Schema 1.1 `schemas/analysis_result.schema.json` | `ec345aaa387ac5119c1bc0bafac93ba015113d210281d638b5a05195077826c7` | 동일 | 보호됨 |

첨부 프로젝트에는 기존 DOG/CAT 기준 결과 JSON과 실제 분석 영상이 포함되어 있지 않아 해당 결과 파일의 SHA256 및 실영상 추론 회귀는 수행하지 못했습니다.

## 검증 결과

- `unittest`: 32개 모두 통과
- Python 문법 검사: `src/*.py` 18개 통과
- Schema JSON 파싱: 1.0, 기존 1.1, 명시적 1.1 보존본, 신규 1.2 모두 통과
- Schema 1.2 정상 결과 및 FAILED 결과 검증 통과
- ROI 없음/빈 배열, 단일·다중 접근, 다중 ROI, 정상 이탈, 영상 종료, Tracking 누락, 거짓 재접근 방지, 최소 체류시간 필터 통과
- 동일 `analysis_id` + 동일 ROI 재사용, 동일 `analysis_id` + 상이 ROI 충돌 거부 통과

## 변경 파일과 이유

| 파일 | 변경 이유 |
|---|---|
| `src/roi_space_analyzer.py` | 이벤트별 시작·종료·유효 체류·종료 이유 생성 |
| `src/run_pipeline.py` | 성공/실패 결과를 Schema 1.2로 생성·검증 |
| `src/generate_analysis_json.py` | 결과 버전과 검증 Schema를 1.2로 전환 |
| `src/pet_behavior_analyzer.py` | 공개 호출 결과를 Schema 1.2로 검증 |
| `src/model_api.py` | API 및 상태 응답 버전을 1.2.0으로 갱신 |
| `schemas/analysis_result_v1.1.schema.json` | 기존 1.1 명시적 보존본 |
| `schemas/analysis_result_v1.2.schema.json` | `visit_events` 및 1.2 버전 계약 정의 |
| `tests/test_roi_space_analyzer.py` | 이벤트 정책 시나리오 검증 |
| `tests/test_space_analysis_schema.py` | Schema 1.2 ROI 계약 검증 |
| `tests/test_pet_behavior_analyzer.py` | 공개 인터페이스, 재사용 및 ROI 충돌 검증 |

## 최신 master 통합 회귀 결과

- 공개 호출 인터페이스와 Schema 1.2 구현을 최신 master 기준 프로젝트에 선별 반영했습니다.
- 단위·계약 테스트 35개가 모두 통과했습니다.
- Python 문법 검사와 Schema 1.0/1.1/1.2 JSON 파싱이 통과했습니다.
- 실제 DOG 영상은 Schema 1.2 `COMPLETED`, Tracking 품질 `GOOD`으로 완료됐습니다.
- 실제 CAT 영상은 Schema 1.2 `COMPLETED`, Tracking 품질 `GOOD`으로 완료됐습니다.
- 실제 DOG 전체 화면 ROI 회귀에서 접근 이벤트 1건과 `end_reason=VIDEO_END`를 확인했습니다.
- Schema 1.2 분석 결과를 기존 Baseline history 갱신 코드가 거부하던 호환 문제를 발견하여, 분석 결과 Schema 1.1과 1.2를 모두 허용하도록 수정하고 회귀 테스트 3개를 추가했습니다.

## 남은 제한사항

- `visit_events`는 기존 Tracking 표본 시점을 기준으로 계산하므로 프레임 간 실제 경계 통과 시각을 보간하지 않습니다.
- Tracking 누락 중 발생한 실제 이탈·재진입은 알 수 없으므로 마지막 확인 상태를 유지합니다.
- AI는 결과만 반환하며 DB 저장은 구현하지 않았습니다.
- LIVE 프레임 입력과 세션 관리는 아직 구현하지 않았습니다.

## 다음 Spring·DB 연결 범위

1. Spring 응답 DTO/검증 모델에 `schema_version=1.2`, `roi-space-v2`, `visit_events`를 추가합니다.
2. `CAMERA_ROI_LOG`는 `visit_events` 한 건당 한 행을 저장합니다.
3. 권장 매핑은 `analysis_id`, `camera_id`, `roi_id`, `event_index`, `entry_time_sec`, `exit_time_sec`, `stay_time_sec`, `end_reason`입니다.
4. `VIDEO_END`에서는 `exit_time_sec`의 DB `NULL`을 허용하고, `end_reason`은 `EXIT`/`VIDEO_END`로 제한합니다.
5. 기존 ROI 집계값은 분석 결과 요약 조회용으로 유지하고 이벤트 행과 합계 일치 여부를 검증합니다.
6. 동일 `analysis_id` 재수신 시 중복 이벤트 삽입을 막는 유니크 키 또는 멱등 저장 정책을 적용합니다.
7. Schema 1.0/1.1 수신 호환이 필요하면 버전별 DTO 또는 선택 필드 처리로 유지하고, 1.2에서만 `visit_events`를 필수 검증합니다.
