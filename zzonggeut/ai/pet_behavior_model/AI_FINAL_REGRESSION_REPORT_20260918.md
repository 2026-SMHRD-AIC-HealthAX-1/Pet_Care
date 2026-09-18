# AI Final Regression Report

- Date: 2026-09-18
- Branch: chore/ai-legacy-cleanup
- Base master: 215fd9a
- Cleanup commit: 547004c
- Schema: 1.2
- Pipeline: pet-behavior-v1.2
- Feature version: pet-features-v2.0
- Detector: YOLO11s

## 1. Static / Unit Validation

- Python syntax: PASS
- Core imports: PASS
- Unit tests: 45 / 45 PASS

Validated areas:
- PetBehaviorAnalyzer
- LivePetBehaviorAnalyzer
- ROI request validation
- ROI space analysis
- Schema 1.1 / 1.2 compatibility
- Baseline history schema
- analysis_id conflict handling
- LIVE interval / timestamp handling

## 2. UPLOAD Real-Video Regression

### DOG

- Video: pet_tracking_test.mp4
- analysis_status: COMPLETED
- schema_version: 1.2
- species: DOG
- tracking_success_rate: 1.0
- quality_status: GOOD
- baseline_status: NOT_READY
- change_status: NOT_EVALUATED

features_overall:
- activity_level: 0.043682
- stationary_ratio: 0.708108
- normalized_travel_distance: 1.010126
- normalized_moving_speed: 0.149650

Result: PASS

### CAT

- Video: cat_tracking_test3.mov
- analysis_status: COMPLETED
- schema_version: 1.2
- species: CAT
- baseline_status: NOT_READY
- change_status: NOT_EVALUATED

features_overall:
- activity_level: 0.052455
- stationary_ratio: 0.440397
- normalized_travel_distance: 1.585001
- normalized_moving_speed: 0.093736

Result: PASS

## 3. LIVE Real-Video Regression

### DOG

- processed_frames: 579
- input_fps: 24.0
- processing_fps: 7.03
- average_frame_latency_sec: 0.1422
- live_status: COMPLETED
- live_schema: 1.2
- upload_status: COMPLETED
- upload_schema: 1.2
- 5-second intervals generated successfully

Functional result: PASS
Performance: WARNING - backlog risk detected

### CAT

- processed_frames: 1872
- input_fps: 59.93
- processing_fps: 7.01
- average_frame_latency_sec: 0.1426
- live_status: COMPLETED
- live_schema: 1.2
- upload_status: COMPLETED
- upload_schema: 1.2
- 5-second intervals generated successfully

Functional result: PASS
Performance: WARNING - backlog risk detected

## 4. ROI / Space Analysis Regression

Real DOG video with two normalized RECTANGLE ROIs.

### ROI-FULL-001

- roi_name: BED
- approach_count: 1
- stay_time_sec: 24.083
- first_approach_time_sec: 0.042
- visit_events: generated
- end_reason: VIDEO_END

### ROI-CENTER-002

- roi_name: WATER_BOWL
- approach_count: 1
- stay_time_sec: 17.25
- first_approach_time_sec: 0.042
- visit_events: generated
- end_reason: EXIT

Validated:
- Multiple ROI handling
- Tracking result reuse
- Approach count
- Stay time
- visit_events
- EXIT
- VIDEO_END

Result: PASS

## 5. Exception Regression

1. Invalid species
   - AnalyzerInputError
   - PASS

2. Video not found
   - analysis_status: FAILED
   - error.code: VIDEO_NOT_FOUND
   - PASS

3. ROI camera mismatch
   - AnalyzerInputError
   - PASS

4. Invalid ROI coordinates
   - AnalyzerInputError
   - PASS

5. Duplicate analysis_id with different request
   - AnalysisConflictError
   - PASS

Exception regression result: 5 / 5 PASS

## 6. AI -> Spring E2E

AI API:
- POST http://localhost:8000/api/v1/analyze
- HTTP 200 OK

Analysis:
- analysis_id: ANL-FINAL-API-E2E-001
- schema_version: 1.2
- analysis_status: COMPLETED
- DOG tracking: 579 / 579 valid frames
- tracking_success_rate: 1.0
- quality_status: GOOD

Spring receiver:
- POST http://localhost:9090/api/ai/analysis-results

Confirmed Spring log:
[AI RESULT RECEIVED] analysis_id=ANL-FINAL-API-E2E-001, schema_version=1.2, analysis_status=COMPLETED

Result: PASS

## 7. Final Status

AI Final Candidate: PASS

Validated:
- UPLOAD DOG / CAT
- LIVE DOG / CAT
- Schema 1.2
- Behavior features
- Baseline NOT_READY policy
- Change NOT_EVALUATED policy
- Multiple ROI
- visit_events
- Failure / validation handling
- FastAPI analysis endpoint
- AI -> Spring result delivery

## 8. Known Limitation

LIVE analysis currently processes approximately 7 FPS in the development environment.

The LIVE input pipeline is functionally operational, but input streams above the processing rate can accumulate backlog.

Future optimization candidates:
- Frame sampling
- Input FPS control
- Detector/model optimization
- Hardware acceleration / GPU environment

This is recorded as a performance optimization item and is not treated as a functional regression failure.

## 9. Remaining Backend / Integration Work

Not part of this AI Final Candidate:

- Spring -> AI POST /api/v1/analyze request implementation
- Spring result validation / DB persistence completion
- ROI DB query integration
- Removal of legacy MonitoringService -> ai/analyze_pet.py path after replacement
- Frontend -> Spring integration
- Full service E2E
