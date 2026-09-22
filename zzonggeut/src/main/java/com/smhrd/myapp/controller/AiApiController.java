package com.smhrd.myapp.controller;


import com.smhrd.myapp.dto.AiModeNotifyDto;
import com.smhrd.myapp.dto.PetAnalysisResultDto;
import com.smhrd.myapp.service.AiModeManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import tools.jackson.databind.ObjectMapper;
import com.smhrd.myapp.mapper.PetAnalysisMapper; // 1. Mapper 임포트 추가

import java.util.HashMap;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequiredArgsConstructor
public class AiApiController 
{
	// 주입받지 않고 직접 생성하여 사용 (에러 방지)
    private final ObjectMapper objectMapper = new ObjectMapper();
    
	private final AiModeManager aiModeManager;
	private final PetAnalysisMapper petAnalysisMapper;

    /**
     * 1. AI 서버 구동 시 모드 알림 수신
     * POST http://localhost:8080/api/ai/mode
     */
    @PostMapping("/api/ai/mode")
    public ResponseEntity<String> receiveAiMode(@RequestBody AiModeNotifyDto dto) {
        aiModeManager.setMode(dto.getMode());
        log.info("[AI 모드 갱신] 현재 모드: {}, 전송시간: {}", dto.getMode(), dto.getTimestamp());
        return ResponseEntity.ok("Mode updated successfully");
    }

    /**
     * 2. [upload 모드] FastAPI가 10초마다 푸시하는 결과 수신
     * POST http://localhost:8080/api/pet/analysis
     */
//    @PostMapping("/api/pet/analysis")
//    public ResponseEntity<String> receiveUploadAnalysis(@RequestBody PetAnalysisResultDto dto) {
//        
//    	try 
//    	{
//            // 수신된 DTO 객체를 들여쓰기(Indent)가 포함된 JSON 문자열로 변환
//    		String prettyJson = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(dto);
//
//    		// 아래 구문은 나중에 디버그 모드에서 사용할수 있으니 
//            System.out.println("==================================================");
//        	log.info("[Upload 모드 수신] 분석 일시: {}", dto.getAnalyzedAt());
//        	log.info("분석 데이터 내용: {}", dto.getData());
//        	
//            System.out.println("[FastAPI 수신 데이터 확인]");
//            System.out.println(prettyJson);
//            System.out.println("==================================================");
//
//        } catch (Exception e) {
//            log.error("JSON 변환 출력 중 에러 발생: {}", e.getMessage());
//        }
//
//        return ResponseEntity.ok("Analysis received successfully");
//    }
    @PostMapping("/api/pet/analysis")
    @SuppressWarnings("unchecked")
    public ResponseEntity<String> receiveUploadAnalysis(@RequestBody PetAnalysisResultDto dto) {
        try {
        	
        	// 수신된 DTO 객체를 들여쓰기(Indent)가 포함된 JSON 문자열로 변환
    		String prettyJson = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(dto);

    		// 아래 구문은 나중에 디버그 모드에서 사용할수 있으니 
            System.out.println("==================================================");
        	log.info("[Upload 모드 수신] 분석 일시: {}", dto.getAnalyzedAt());
        	log.info("분석 데이터 내용: {}", dto.getData());
        	
            System.out.println("[FastAPI 수신 데이터 확인]");
            System.out.println(prettyJson);
            System.out.println("==================================================");
        	
            Map<String, Object> data = dto.getData();
            if (data == null) {
                return ResponseEntity.badRequest().body("Data is null");
            }

            Map<String, Object> featuresOverall = (Map<String, Object>) data.get("features_overall");
            Map<String, Object> changeDetection = (Map<String, Object>) data.get("change_detection");

            // 별도 DTO 없이 Map에 16개 데이터 직접 적재
            Map<String, Object> paramMap = new HashMap<>();

            // (1) 기본 정보 (9개)
            paramMap.put("analysisId", data.get("analysis_id"));
            paramMap.put("schemaVersion", data.get("schema_version"));
            paramMap.put("petId", data.get("pet_id"));
            paramMap.put("videoId", data.get("video_id"));
            paramMap.put("cameraId", data.get("camera_id"));
            paramMap.put("species", data.get("species"));
            paramMap.put("recordedAt", data.get("recorded_at"));
            paramMap.put("timeSlot", data.get("time_slot"));
            paramMap.put("analysisStatus", data.get("analysis_status"));

            // (2) 대표 수치 (4개)
            paramMap.put("activityLevel", featuresOverall != null ? featuresOverall.get("activity_level") : 0.0);
            paramMap.put("stationaryRatio", featuresOverall != null ? featuresOverall.get("stationary_ratio") : 0.0);
            paramMap.put("normalizedTravelDistance", featuresOverall != null ? featuresOverall.get("normalized_travel_distance") : 0.0);
            paramMap.put("normalizedMovingSpeed", featuresOverall != null ? featuresOverall.get("normalized_moving_speed") : 0.0);

            // (3) 변화 감지 (3개)
            paramMap.put("baselineStatus", changeDetection != null ? changeDetection.get("baseline_status") : null);
            paramMap.put("changeStatus", changeDetection != null ? changeDetection.get("change_status") : null);
            paramMap.put("changeScore", changeDetection != null ? changeDetection.get("change_score") : null);

            // Mapper에 Map 전달
            petAnalysisMapper.insertBehaviorMap(paramMap);
            
            log.info("[DB 저장 완료] analysis_id: {}", paramMap.get("analysisId"));
            return ResponseEntity.ok("Successfully saved to DB");

        } catch (Exception e) {
            log.error("[DB 저장 실패] 오류: ", e);
            return ResponseEntity.internalServerError().body("DB Error: " + e.getMessage());
        }
    }
        @GetMapping("/api/pet/analysis/latest")
    public ResponseEntity<?> getLatestAnalysis() {

        Map<String, Object> result = petAnalysisMapper.selectLatestBehaviorMap();

        if (result == null || result.isEmpty()) {
            return ResponseEntity.noContent().build();
        }

        return ResponseEntity.ok(result);
    }
}
