package com.smhrd.myapp.controller;

import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import com.smhrd.myapp.dto.PetActRecordRequestDto;
import com.smhrd.myapp.entity.PetActRecord;
import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.PetActRecordRepository;
import com.smhrd.myapp.repository.PetRepository;

import jakarta.servlet.http.HttpSession;

@RestController
@RequestMapping("/api/monitoring")
public class VideoMonitoringController {

    private final PetActRecordRepository petActRecordRepository;
    private final PetRepository petRepository;

    private static final String PYTHON_AI_URL =
            "http://localhost:8000/api/ai/upload-and-analyze";

    private static final ZoneId KST =
            ZoneId.of("Asia/Seoul");

    public VideoMonitoringController(
            PetActRecordRepository petActRecordRepository,
            PetRepository petRepository
    ) {
        this.petActRecordRepository =
                petActRecordRepository;

        this.petRepository =
                petRepository;
    }


    // =========================================================
    // 기존 영상 AI 요청 API
    // =========================================================
    @PostMapping("/run-video-ai")
    public ResponseEntity<?> runAiAnalysis(
            @RequestParam("video") MultipartFile videoFile,
            @RequestParam(
                    value = "pet_id",
                    defaultValue = "PET-001"
            ) String petId,
            @RequestParam(
                    defaultValue = "DOG"
            ) String species,
            @RequestParam(
                    value = "roi_data",
                    required = false
            ) String roiData,
            HttpSession session
    ) {

        if (
                videoFile == null
                || videoFile.isEmpty()
        ) {
            return ResponseEntity
                    .badRequest()
                    .body(
                            "업로드된 영상이 비어있습니다."
                    );
        }


        try {

            // =================================================
            // 1. 로그인 사용자 확인
            // =================================================
            String loginUserSeq =
                    "admin";

            Object sessionUser =
                    session.getAttribute(
                            "loginUser"
                    );


            if (
                    sessionUser
                            instanceof UserEntity
            ) {

                loginUserSeq =
                        ((UserEntity) sessionUser)
                                .getId();

            } else if (
                    sessionUser != null
            ) {

                loginUserSeq =
                        sessionUser.toString();
            }


            // =================================================
            // 2. 현재 로그인 유저의 첫 번째 PET 조회
            //
            // 이 API는 현재 legacy 경로이므로 기존 동작 유지.
            // 실제 Dashboard 업로드는 MonitoringService 기반
            // /api/monitoring/run-ai 흐름을 사용.
            // =================================================
            String actualPetId =
                    "1";

            List<PetEntity> petList =
                    petRepository
                            .findByUser_seq(
                                    loginUserSeq
                            );


            if (
                    petList != null
                    && !petList.isEmpty()
            ) {

                actualPetId =
                        String.valueOf(
                                petList
                                        .get(0)
                                        .getSeq()
                        );
            }


            // =================================================
            // 3. Python AI 서버 Multipart 구성
            // =================================================
            HttpHeaders headers =
                    new HttpHeaders();

            headers.setContentType(
                    MediaType
                            .MULTIPART_FORM_DATA
            );


            MultiValueMap<String, Object> body =
                    new LinkedMultiValueMap<>();


            ByteArrayResource fileResource =
                    new ByteArrayResource(
                            videoFile.getBytes()
                    ) {

                        @Override
                        public String getFilename() {

                            return videoFile
                                    .getOriginalFilename();
                        }
                    };


            body.add(
                    "file",
                    fileResource
            );

            body.add(
                    "pet_id",
                    actualPetId
            );

            body.add(
                    "user_seq",
                    loginUserSeq
            );

            body.add(
                    "video_id",
                    "VID-"
                            + System.currentTimeMillis()
            );

            body.add(
                    "camera_id",
                    "CAM-001"
            );

            body.add(
                    "species",
                    species
            );


            if (
                    roiData != null
                    && !roiData
                            .trim()
                            .isEmpty()
            ) {

                body.add(
                        "roi_data",
                        roiData
                );
            }


            HttpEntity<
                    MultiValueMap<
                            String,
                            Object
                    >
                    > requestEntity =
                    new HttpEntity<>(
                            body,
                            headers
                    );


            RestTemplate restTemplate =
                    new RestTemplate();


            ResponseEntity<String> pythonResponse =
                    restTemplate
                            .postForEntity(
                                    PYTHON_AI_URL,
                                    requestEntity,
                                    String.class
                            );


            return ResponseEntity
                    .status(
                            pythonResponse
                                    .getStatusCode()
                    )
                    .body(
                            pythonResponse
                                    .getBody()
                    );


        } catch (
                IOException e
        ) {

            return ResponseEntity
                    .status(
                            HttpStatus
                                    .INTERNAL_SERVER_ERROR
                    )
                    .body(
                            "파일 처리 실패: "
                                    + e.getMessage()
                    );

        } catch (
                Exception e
        ) {

            return ResponseEntity
                    .status(
                            HttpStatus
                                    .INTERNAL_SERVER_ERROR
                    )
                    .body(
                            "파이썬 AI 서버 통신 오류: "
                                    + e.getMessage()
                    );
        }
    }


    // =========================================================
    // ROI 요약 기록 직접 저장 API
    // =========================================================
    @PostMapping("/save-roi-records")
    public ResponseEntity<?> saveRoiRecords(
            @RequestBody
            List<PetActRecordRequestDto> dtos,
            HttpSession session
    ) {

        if (
                dtos == null
                || dtos.isEmpty()
        ) {

            return ResponseEntity
                    .badRequest()
                    .body(
                            "저장할 데이터가 없습니다."
                    );
        }


        // =====================================================
        // 1. 로그인 사용자
        // =====================================================
        String loginUserSeq =
                "admin";

        Object sessionUser =
                session.getAttribute(
                        "loginUser"
                );


        if (
                sessionUser
                        instanceof UserEntity
        ) {

            UserEntity user =
                    (UserEntity) sessionUser;

            loginUserSeq =
                    user.getId();

        } else if (
                sessionUser
                        instanceof String
        ) {

            loginUserSeq =
                    (String) sessionUser;
        }


        // =====================================================
        // 2. 사용자 첫 번째 PET
        // 기존 API 동작 유지
        // =====================================================
        Integer targetPetSeq =
                1;


        List<PetEntity> petList =
                petRepository
                        .findByUser_seq(
                                loginUserSeq
                        );


        if (
                petList != null
                && !petList.isEmpty()
        ) {

            targetPetSeq =
                    petList
                            .get(0)
                            .getSeq();
        }


        // =====================================================
        // 3. ROI 저장
        // =====================================================
        LocalDateTime now =
                LocalDateTime.now(
                        KST
                );


        List<PetActRecord> entities =
                new ArrayList<>();


        for (
                int i = 0;
                i < dtos.size();
                i++
        ) {

            PetActRecordRequestDto dto =
                    dtos.get(i);


            PetActRecord entity =
                    PetActRecord
                            .builder()
                            .dttm(
                                    now.plusSeconds(
                                            i
                                    )
                            )
                            .petSeq(
                                    targetPetSeq
                            )
                            .userSeq(
                                    loginUserSeq
                            )
                            .roiName(
                                    dto.getRoiName()
                            )
                            .continueTime(
                                    dto.getContinueTime()
                            )
                            .stopRatio(
                                    dto.getStopRatio()
                            )
                            .build();


            entities.add(
                    entity
            );
        }


        petActRecordRepository
                .saveAll(
                        entities
                );


        return ResponseEntity.ok(
                "저장 성공 "
                        + "(USER_SEQ: "
                        + loginUserSeq
                        + ", PET_SEQ: "
                        + targetPetSeq
                        + ")"
        );
    }


    // =========================================================
    // 오늘 ROI 체류 비율 조회
    //
    // 핵심 수정:
    // pet_id가 전달되면 선택된 PET 기준 조회
    // + 현재 로그인 사용자의 PET인지 검증
    // =========================================================
    @GetMapping("/today-stay-ratio")
    public ResponseEntity<?> getTodayStayRatio(
            @RequestParam(
                    value = "pet_id",
                    required = false
            ) Integer requestedPetSeq,
            HttpSession session
    ) {

        // =====================================================
        // 1. 로그인 사용자 확인
        // =====================================================
        Object sessionUser =
                session.getAttribute(
                        "loginUser"
                );


        if (
                !(
                        sessionUser
                                instanceof UserEntity
                )
        ) {

            return ResponseEntity
                    .status(
                            HttpStatus.UNAUTHORIZED
                    )
                    .body(
                            Map.of(
                                    "message",
                                    "로그인이 필요한 서비스입니다."
                            )
                    );
        }


        UserEntity loginUser =
                (UserEntity) sessionUser;


        String loginUserSeq =
                loginUser.getId();


        // =====================================================
        // 2. 로그인 사용자의 PET 목록 조회
        // =====================================================
        List<PetEntity> petList =
                petRepository
                        .findByUser_seq(
                                loginUserSeq
                        );


        // 등록된 PET 없음
        if (
                petList == null
                || petList.isEmpty()
        ) {

            return ResponseEntity.ok(
                    Map.of(
                            "petSeq",
                            0,
                            "totalStayTime",
                            0,
                            "ratios",
                            List.of()
                    )
            );
        }


        // =====================================================
        // 3. 조회 대상 PET 결정
        // =====================================================
        Integer targetPetSeq;


        if (
                requestedPetSeq != null
        ) {

            PetEntity matchedPet =
                    petList
                            .stream()
                            .filter(
                                    pet ->
                                            pet.getSeq()
                                                    != null
                                            && pet.getSeq()
                                                    .equals(
                                                            requestedPetSeq
                                                    )
                            )
                            .findFirst()
                            .orElse(
                                    null
                            );


            // 다른 사용자의 PET 또는 없는 PET
            if (
                    matchedPet == null
            ) {

                return ResponseEntity
                        .status(
                                HttpStatus.FORBIDDEN
                        )
                        .body(
                                Map.of(
                                        "message",
                                        "조회할 수 없는 반려동물입니다."
                                )
                        );
            }


            targetPetSeq =
                    matchedPet.getSeq();

        } else {

            // ---------------------------------------------
            // 기존 호출 하위 호환
            // Dashboard 연결 후에는 거의 사용되지 않음
            // ---------------------------------------------
            targetPetSeq =
                    petList
                            .get(0)
                            .getSeq();
        }


        // =====================================================
        // 4. 오늘 날짜 범위
        // =====================================================
        LocalDate today =
                LocalDate.now(
                        KST
                );


        LocalDateTime startOfDay =
                today.atStartOfDay();


        LocalDateTime endOfDay =
                today.atTime(
                        LocalTime.MAX
                );


        // =====================================================
        // 5. 선택 PET의 ROI 기록 조회
        // =====================================================
        List<PetActRecord> records =
                petActRecordRepository
                        .findTodayRecords(
                                loginUserSeq,
                                targetPetSeq,
                                startOfDay,
                                endOfDay
                        );


        // =====================================================
        // 6. ROI 기록 없음
        // =====================================================
        if (
                records == null
                || records.isEmpty()
        ) {

            return ResponseEntity.ok(
                    Map.of(
                            "petSeq",
                            targetPetSeq,
                            "totalStayTime",
                            0,
                            "ratios",
                            List.of()
                    )
            );
        }


        // =====================================================
        // 7. ROI별 체류시간 합산
        // =====================================================
        Map<String, Integer> stayByRoi =
                records
                        .stream()
                        .filter(
                                record ->
                                        record.getRoiName()
                                                != null
                        )
                        .collect(
                                Collectors.groupingBy(
                                        PetActRecord
                                                ::getRoiName,

                                        Collectors
                                                .summingInt(
                                                        record ->
                                                                record
                                                                        .getContinueTime()
                                                                        != null
                                                                        ? record
                                                                                .getContinueTime()
                                                                        : 0
                                                )
                                )
                        );


        // =====================================================
        // 8. 전체 체류시간
        // =====================================================
        int totalStayTime =
                stayByRoi
                        .values()
                        .stream()
                        .mapToInt(
                                Integer::intValue
                        )
                        .sum();


        // =====================================================
        // 9. ROI별 비율
        // =====================================================
        List<Map<String, Object>> ratioList =
                new ArrayList<>();


        for (
                Map.Entry<
                        String,
                        Integer
                        > entry
                        : stayByRoi
                                .entrySet()
        ) {

            String roiName =
                    entry.getKey();


            int stayTime =
                    entry.getValue();


            int percent =
                    totalStayTime > 0

                            ? (int) Math.round(
                                    (
                                            (double) stayTime
                                            / totalStayTime
                                    )
                                            * 100
                            )

                            : 0;


            Map<String, Object> item =
                    new HashMap<>();


            item.put(
                    "roiName",
                    roiName
            );

            item.put(
                    "stayTime",
                    stayTime
            );

            item.put(
                    "percent",
                    percent
            );


            ratioList.add(
                    item
            );
        }


        // =====================================================
        // 10. 비율 높은 순서 정렬
        // =====================================================
        ratioList.sort(
                (a, b) ->
                        Integer.compare(
                                (Integer) b.get(
                                        "percent"
                                ),
                                (Integer) a.get(
                                        "percent"
                                )
                        )
        );


        // =====================================================
        // 11. 최종 응답
        // =====================================================
        return ResponseEntity.ok(
                Map.of(
                        "petSeq",
                        targetPetSeq,
                        "totalStayTime",
                        totalStayTime,
                        "ratios",
                        ratioList
                )
        );
    }
}