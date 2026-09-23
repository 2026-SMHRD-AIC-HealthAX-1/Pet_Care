package com.smhrd.myapp.controller;

import com.smhrd.myapp.entity.UserEntity;
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
import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.repository.PetActRecordRepository;
import com.smhrd.myapp.repository.PetRepository;

import jakarta.servlet.http.HttpSession;
import jakarta.websocket.Session;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;

import com.smhrd.myapp.entity.UserEntity; // 🌟 1. UserEntity import 추가!
import java.time.LocalDateTime;
import java.time.ZoneId; // 🌟 한국 시간대 지정을 위해 추가
import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/monitoring")
public class VideoMonitoringController 
{
	private final PetActRecordRepository petActRecordRepository;
	private final PetRepository petRepository; // 👈 1. 추가
	private final String PYTHON_AI_URL = "http://localhost:8000/api/ai/upload-and-analyze";

	public VideoMonitoringController(PetActRecordRepository petActRecordRepository, PetRepository petRepository) {
        this.petActRecordRepository = petActRecordRepository;
        this.petRepository = petRepository;
    }

    @PostMapping("/run-video-ai")
    public ResponseEntity<?> runAiAnalysis(
            @RequestParam("video") MultipartFile videoFile,
            @RequestParam(value = "pet_id", defaultValue = "PET-001") String petId,
            @RequestParam(defaultValue = "DOG") String species,
            @RequestParam(value = "roi_data", required = false) String roiData,
            HttpSession session // 🌟 세션 주입
            ) {
        if (videoFile.isEmpty()) {
            return ResponseEntity.badRequest().body("업로드된 영상이 비어있습니다.");
        }

        try {
        	// 🌟 1. 세션에서 로그인한 USER_SEQ 꺼내기
            String loginUserSeq = "admin";
            Object sessionUser = session.getAttribute("loginUser");
            if (sessionUser instanceof UserEntity) {
                loginUserSeq = ((UserEntity) sessionUser).getId();
            } else if (sessionUser != null) {
                loginUserSeq = sessionUser.toString();
            }

            // 🌟 2. DB에서 유저의 첫 번째 펫 SEQ 조회
            String actualPetId = "1";
            List<PetEntity> petList = petRepository.findByUser_seq(loginUserSeq);
            if (petList != null && !petList.isEmpty()) {
                actualPetId = String.valueOf(petList.get(0).getSeq());
            }
            
            // 3. 파이썬 서버로 보낼 Multipart 요청 구성
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

            body.add("pet_id", actualPetId);
            body.add("user_seq", loginUserSeq);
            body.add("video_id", "VID-" + System.currentTimeMillis());
            body.add("camera_id", "CAM-001");
            body.add("species", species);

            // 🌟 4. ROI 데이터가 넘어온 경우 파이썬 전송 폼에 추가
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
    public ResponseEntity<?> saveRoiRecords(@RequestBody List<PetActRecordRequestDto> dtos, HttpSession session) {
    	if (dtos == null || dtos.isEmpty()) {
            return ResponseEntity.badRequest().body("저장할 데이터가 없습니다.");
        }

        // 🌟 1. 세션에서 UserEntity 객체를 꺼내 String 타입의 USER_SEQ(아이디) 추출
        String loginUserSeq = "admin"; // 미로그인/테스트 시 기본값
        Object sessionUser = session.getAttribute("loginUser");

        if (sessionUser instanceof UserEntity) {
            UserEntity user = (UserEntity) sessionUser;
            // ※ UserEntity에 선언된 아이디 getter 호출 (예: user.getUser_seq(), user.getUserId(), user.getUserSeq() 등)
            loginUserSeq = user.getId(); 
        } else if (sessionUser instanceof String) {
            loginUserSeq = (String) sessionUser;
        }

        // 🌟 2. String 유저 ID로 DB(PET_INFO)에서 반려동물 조회 -> Integer PET_SEQ 추출
        Integer targetPetSeq = 1; // 기본값
        List<PetEntity> petList = petRepository.findByUser_seq(loginUserSeq);
        if (petList != null && !petList.isEmpty()) {
            targetPetSeq = petList.get(0).getSeq(); // 👈 PET_INFO의 PK(Integer seq)
        }

        // 🌟 3. 한국 표준시(KST)로 현재 시각 고정 (9시간 오차 해결)
        LocalDateTime now = LocalDateTime.now(ZoneId.of("Asia/Seoul"));
        List<PetActRecord> entities = new ArrayList<>();

        for (int i = 0; i < dtos.size(); i++) {
            PetActRecordRequestDto dto = dtos.get(i);

            PetActRecord entity = PetActRecord.builder()
                    .dttm(now.plusSeconds(i)) // 동일 시점 PK 충돌 방지용 나노초/초 시차
                    .petSeq(targetPetSeq)     // Integer 타입 펫 번호
                    .userSeq(loginUserSeq)    // String 타입 유저 ID
                    .roiName(dto.getRoiName())
                    .continueTime(dto.getContinueTime())
                    .stopRatio(dto.getStopRatio())
                    .build();

            entities.add(entity);
        }

        petActRecordRepository.saveAll(entities);

        return ResponseEntity.ok("저장 성공 (USER_SEQ: " + loginUserSeq + ", PET_SEQ: " + targetPetSeq + ")");
    }
}
