package com.smhrd.myapp.controller;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

import com.smhrd.myapp.dto.PetActRecordRequestDto;
import com.smhrd.myapp.entity.PetActRecord;
import com.smhrd.myapp.repository.PetActRecordRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/monitoring")
public class VideoMonitoringController 
{
	private final PetActRecordRepository petActRecordRepository;
	private final String PYTHON_AI_URL = "http://localhost:8000/api/ai/upload-and-analyze";

	VideoMonitoringController(PetActRecordRepository petActRecordRepository) {
		this.petActRecordRepository = petActRecordRepository;
	}

    @PostMapping("/run-video-ai")
    public ResponseEntity<?> runAiAnalysis(
            @RequestParam("video") MultipartFile videoFile,
            @RequestParam(value = "pet_id", defaultValue = "PET-001") String petId,
            @RequestParam(defaultValue = "DOG") String species,
            @RequestParam(value = "roi_data", required = false) String roiData
            ) {
        if (videoFile.isEmpty()) {
            return ResponseEntity.badRequest().body("업로드된 영상이 비어있습니다.");
        }

        try {
            // 1. 파이썬 서버로 보낼 Multipart 요청 구성
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();

            // MultipartFile의 원본 파일명과 바이트 데이터를 ByteArrayResource로 변환
            ByteArrayResource fileResource = new ByteArrayResource(videoFile.getBytes()) {
                @Override
                public String getFilename() {
                    return videoFile.getOriginalFilename();
                }
            };

            body.add("file", fileResource);
            body.add("pet_id", petId);
            body.add("video_id", "VID-" + System.currentTimeMillis());
            body.add("camera_id", "CAM-001");
            body.add("species", species);

            // 🌟 2. ROI 데이터가 넘어온 경우 파이썬 전송 폼에 추가
            if (roiData != null && !roiData.trim().isEmpty()) {
                body.add("roi_data", roiData);
            }
            
            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            // 2. 파이썬 AI 서버로 전송
            RestTemplate restTemplate = new RestTemplate();
            ResponseEntity<String> pythonResponse = restTemplate.postForEntity(PYTHON_AI_URL, requestEntity, String.class);

            // 3. 파이썬 서버의 작업 성공 응답을 프론트 브라우저에 그대로 반환
            return ResponseEntity.status(pythonResponse.getStatusCode()).body(pythonResponse.getBody());

        } catch (IOException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("파일 처리 실패: " + e.getMessage());
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("파이썬 AI 서버 통신 오류: " + e.getMessage());
        }
    }
    
    @PostMapping("/save-roi-records")
    public ResponseEntity<?> saveRoiRecords(@RequestBody List<PetActRecordRequestDto> dtos) {
        if (dtos == null || dtos.isEmpty()) {
            return ResponseEntity.badRequest().body("저장할 데이터가 없습니다.");
        }

        LocalDateTime now = LocalDateTime.now();
        List<PetActRecord> entities = new ArrayList<>();

        for (int i = 0; i < dtos.size(); i++) {
            PetActRecordRequestDto dto = dtos.get(i);

            PetActRecord entity = PetActRecord.builder()
                    // DTTM이 단독 PK이므로 동일 시점 레코드 간 충돌 방지를 위해 나노초 단위 시차 부여
            		.dttm(now.plusSeconds(i))
                    .petSeq(dto.getPetSeq() != null ? dto.getPetSeq() : 1)
                    .userSeq(dto.getUserSeq() != null ? dto.getUserSeq() : "admin")
                    .roiName(dto.getRoiName())
                    .continueTime(dto.getContinueTime())
                    .stopRatio(dto.getStopRatio())
                    .build();

            entities.add(entity);
        }

        // JPA 일괄 저장 (Batch Insert)
        petActRecordRepository.saveAll(entities);

        return ResponseEntity.ok("JPA를 통한 데이터 저장이 완료되었습니다.");
    }
}
