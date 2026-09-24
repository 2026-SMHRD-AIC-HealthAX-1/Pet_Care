package com.smhrd.myapp.controller;

import com.smhrd.myapp.dto.AiModeNotifyDto;
import com.smhrd.myapp.dto.PetAnalysisResultDto;
import com.smhrd.myapp.entity.PetActRecord;
import com.smhrd.myapp.mapper.PetAnalysisMapper;
import com.smhrd.myapp.repository.PetActRecordRepository;
import com.smhrd.myapp.service.AiModeManager;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import tools.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequiredArgsConstructor
public class AiApiController {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    // 기존 구조 유지
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final AiModeManager aiModeManager;
    private final PetAnalysisMapper petAnalysisMapper;
    private final PetActRecordRepository petActRecordRepository;

    /**
     * AI 서버 구동 시 모드 알림 수신
     */
    @PostMapping("/api/ai/mode")
    public ResponseEntity<String> receiveAiMode(
            @RequestBody AiModeNotifyDto dto
    ) {
        aiModeManager.setMode(dto.getMode());

        log.info(
                "[AI 모드 갱신] 현재 모드: {}, 전송시간: {}",
                dto.getMode(),
                dto.getTimestamp()
        );

        return ResponseEntity.ok(
                "Mode updated successfully"
        );
    }

    /**
     * UPLOAD / LIVE 공통 AI 결과 수신
     *
     * 1) RECEIVE_AI_DATA 저장
     * 2) space_analysis.roi_results가 있으면 PET_ACT_RECORD 저장
     */
    @PostMapping("/api/pet/analysis")
    @SuppressWarnings("unchecked")
    public ResponseEntity<String> receiveUploadAnalysis(
            @RequestBody PetAnalysisResultDto dto
    ) {
        try {
            String prettyJson =
                    objectMapper
                            .writerWithDefaultPrettyPrinter()
                            .writeValueAsString(dto);

            System.out.println(
                    "=================================================="
            );

            log.info(
                    "[AI 분석 결과 수신] mode={}, 분석 일시={}",
                    dto.getMode(),
                    dto.getAnalyzedAt()
            );

            log.info(
                    "분석 데이터 내용: {}",
                    dto.getData()
            );

            System.out.println(
                    "[FastAPI 수신 데이터 확인]"
            );
            System.out.println(prettyJson);

            System.out.println(
                    "=================================================="
            );

            Map<String, Object> data =
                    dto.getData();

            if (data == null) {
                return ResponseEntity
                        .badRequest()
                        .body("Data is null");
            }

            Map<String, Object> featuresOverall =
                    (Map<String, Object>)
                            data.get(
                                    "features_overall"
                            );

            Map<String, Object> changeDetection =
                    (Map<String, Object>)
                            data.get(
                                    "change_detection"
                            );

            Map<String, Object> paramMap =
                    new HashMap<>();

            // ------------------------------
            // 1. RECEIVE_AI_DATA 저장
            // ------------------------------

            String mode = dto.getMode();

            if (
                    mode == null
                    || mode.isBlank()
            ) {
                mode = aiModeManager.getMode();
            }

            if (
                    mode == null
                    || mode.isBlank()
            ) {
                mode = "unknown";
            }

            paramMap.put(
                    "gubun",
                    mode
            );

            paramMap.put(
                    "analysisId",
                    data.get("analysis_id")
            );

            paramMap.put(
                    "schemaVersion",
                    data.get("schema_version")
            );

            paramMap.put(
                    "petId",
                    data.get("pet_id")
            );

            paramMap.put(
                    "userSeq",
                    data.get("user_seq")
            );

            paramMap.put(
                    "videoId",
                    data.get("video_id")
            );

            paramMap.put(
                    "cameraId",
                    data.get("camera_id")
            );

            paramMap.put(
                    "species",
                    data.get("species")
            );

            paramMap.put(
                    "recordedAt",
                    data.get("recorded_at")
            );

            paramMap.put(
                    "timeSlot",
                    data.get("time_slot")
            );

            paramMap.put(
                    "analysisStatus",
                    data.get("analysis_status")
            );

            paramMap.put(
                    "activityLevel",
                    featuresOverall != null
                            ? featuresOverall.get(
                                    "activity_level"
                            )
                            : 0.0
            );

            paramMap.put(
                    "stationaryRatio",
                    featuresOverall != null
                            ? featuresOverall.get(
                                    "stationary_ratio"
                            )
                            : 0.0
            );

            paramMap.put(
                    "normalizedTravelDistance",
                    featuresOverall != null
                            ? featuresOverall.get(
                                    "normalized_travel_distance"
                            )
                            : 0.0
            );

            paramMap.put(
                    "normalizedMovingSpeed",
                    featuresOverall != null
                            ? featuresOverall.get(
                                    "normalized_moving_speed"
                            )
                            : 0.0
            );

            paramMap.put(
                    "baselineStatus",
                    changeDetection != null
                            ? changeDetection.get(
                                    "baseline_status"
                            )
                            : null
            );

            paramMap.put(
                    "changeStatus",
                    changeDetection != null
                            ? changeDetection.get(
                                    "change_status"
                            )
                            : null
            );

            paramMap.put(
                    "changeScore",
                    changeDetection != null
                            ? changeDetection.get(
                                    "change_score"
                            )
                            : null
            );

            petAnalysisMapper.insertBehaviorMap(
                    paramMap
            );

            log.info(
                    "[RECEIVE_AI_DATA 저장 완료] analysis_id={}",
                    paramMap.get("analysisId")
            );

            // ------------------------------
            // 2. PET_ACT_RECORD 저장
            // ------------------------------
            // ROI 저장 실패가 핵심 행동분석 저장까지
            // 롤백시키지 않도록 별도 try/catch로 처리.
            try {
                saveSpaceAnalysisRecords(
                        data
                );
            } catch (Exception roiSaveError) {
                log.error(
                        "[PET_ACT_RECORD 저장 실패] analysis_id={}",
                        data.get("analysis_id"),
                        roiSaveError
                );
            }

            return ResponseEntity.ok(
                    "Successfully saved to DB"
            );

        } catch (Exception e) {
            log.error(
                    "[DB 저장 실패] 오류: ",
                    e
            );

            return ResponseEntity
                    .internalServerError()
                    .body(
                            "DB Error: "
                            + e.getMessage()
                    );
        }
    }

    /**
     * AI의 space_analysis.roi_results를
     * PET_ACT_RECORD로 변환하여 저장한다.
     */
    @SuppressWarnings("unchecked")
    private void saveSpaceAnalysisRecords(
            Map<String, Object> data
    ) {
        Object spaceRaw =
                data.get("space_analysis");

        if (!(spaceRaw instanceof Map<?, ?>)) {
            log.info(
                    "[PET_ACT_RECORD] space_analysis 없음 - 저장 생략"
            );
            return;
        }

        Map<String, Object> spaceAnalysis =
                (Map<String, Object>) spaceRaw;

        Object roiRaw =
                spaceAnalysis.get(
                        "roi_results"
                );

        if (!(roiRaw instanceof List<?> roiList)
                || roiList.isEmpty()) {
            log.info(
                    "[PET_ACT_RECORD] roi_results 없음 - 저장 생략"
            );
            return;
        }

        Integer petSeq =
                parsePetSeq(
                        data.get("pet_id")
                );

        String userSeq =
                data.get("user_seq") != null
                        ? String.valueOf(
                                data.get("user_seq")
                        ).trim()
                        : null;

        if (
                petSeq == null
                || userSeq == null
                || userSeq.isBlank()
        ) {
            log.warn(
                    "[PET_ACT_RECORD] pet_id/user_seq 부족 - 저장 생략. pet_id={}, user_seq={}",
                    data.get("pet_id"),
                    data.get("user_seq")
            );
            return;
        }

        double videoDurationSec =
                extractVideoDurationSec(
                        data
                );

        LocalDateTime baseTime =
                LocalDateTime.now(KST);

        List<PetActRecord> entities =
                new ArrayList<>();

        int index = 0;

        for (Object roiObject : roiList) {
            if (!(roiObject instanceof Map<?, ?>)) {
                continue;
            }

            Map<String, Object> roi =
                    (Map<String, Object>)
                            roiObject;

            String roiName =
                    roi.get("roi_name") != null
                            ? String.valueOf(
                                    roi.get("roi_name")
                            )
                            : "UNKNOWN";

            double stayTimeSec =
                    toDouble(
                            roi.get(
                                    "stay_time_sec"
                            )
                    );

            // 현재 DB CONTINUE_TIME이 Integer이므로
            // 양수 체류는 최소 1초로 보존한다.
            int storedStaySeconds =
                    toStoredSeconds(
                            stayTimeSec
                    );

            float stopRatio = 0.0f;

            if (
                    videoDurationSec > 0
                    && stayTimeSec > 0
            ) {
                stopRatio =
                        (float) (
                                stayTimeSec
                                / videoDurationSec
                        );
            }

            PetActRecord entity =
                    PetActRecord
                            .builder()
                            .dttm(
                                    baseTime.plusSeconds(
                                            index
                                    )
                            )
                            .petSeq(
                                    petSeq
                            )
                            .userSeq(
                                    userSeq
                            )
                            .roiName(
                                    roiName
                            )
                            .continueTime(
                                    storedStaySeconds
                            )
                            .stopRatio(
                                    stopRatio
                            )
                            .build();

            entities.add(entity);
            index++;
        }

        if (entities.isEmpty()) {
            return;
        }

        petActRecordRepository.saveAll(
                entities
        );

        log.info(
                "[PET_ACT_RECORD 저장 완료] analysis_id={}, count={}",
                data.get("analysis_id"),
                entities.size()
        );
    }

    private Integer parsePetSeq(
            Object petId
    ) {
        if (petId == null) {
            return null;
        }

        try {
            return Integer.valueOf(
                    String.valueOf(
                            petId
                    ).trim()
            );
        } catch (NumberFormatException e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private double extractVideoDurationSec(
            Map<String, Object> data
    ) {
        Object videoInfoRaw =
                data.get("video_info");

        if (!(videoInfoRaw instanceof Map<?, ?>)) {
            return 0.0;
        }

        Map<String, Object> videoInfo =
                (Map<String, Object>)
                        videoInfoRaw;

        return toDouble(
                videoInfo.get(
                        "duration_sec"
                )
        );
    }

    private double toDouble(
            Object value
    ) {
        if (value == null) {
            return 0.0;
        }

        if (value instanceof Number number) {
            return number.doubleValue();
        }

        try {
            return Double.parseDouble(
                    String.valueOf(
                            value
                    )
            );
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }

    private int toStoredSeconds(
            double stayTimeSec
    ) {
        if (stayTimeSec <= 0) {
            return 0;
        }

        return Math.max(
                1,
                (int) Math.round(
                        stayTimeSec
                )
        );
    }

    @GetMapping("/api/pet/analysis/latest")
    public ResponseEntity<?> getLatestAnalysis() {

        Map<String, Object> result =
                petAnalysisMapper
                        .selectLatestBehaviorMap();

        if (
                result == null
                || result.isEmpty()
        ) {
            return ResponseEntity
                    .noContent()
                    .build();
        }

        return ResponseEntity.ok(
                result
        );
    }
}
