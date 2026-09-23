package com.smhrd.myapp.controller;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.PetRepository;
import com.smhrd.myapp.service.MonitoringService;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/monitoring")
public class MonitoringController {

    private final MonitoringService monitoringService;
    private final PetRepository petRepository;

    @PostMapping("/run-ai")
    public ResponseEntity<?> runAiAnalysis(
            @RequestParam("video") MultipartFile video,
            @RequestParam("petId") Integer petId,
            @RequestParam(defaultValue = "CAM-001") String cameraId,
            HttpSession session) {

        try {
            Object sessionUser =
                    session.getAttribute("loginUser");

            if (!(sessionUser instanceof UserEntity)) {
                throw new IllegalArgumentException(
                        "로그인 사용자 정보를 확인할 수 없습니다."
                );
            }

            UserEntity loginUser =
                    (UserEntity) sessionUser;

            String loginUserId =
                    loginUser.getId();

            PetEntity pet =
                    petRepository.findById(petId)
                            .orElseThrow(() ->
                                    new IllegalArgumentException(
                                            "선택한 반려동물 정보를 찾을 수 없습니다."
                                    )
                            );

            if (pet.getUser_seq() == null
                    || !pet.getUser_seq().equals(loginUserId)) {

                throw new IllegalArgumentException(
                        "현재 로그인 사용자의 반려동물이 아닙니다."
                );
            }

            String species =
                    normalizeSpecies(
                            pet.getPSpecies()
                    );

            Map<String, Object> result =
                    monitoringService.analyzeVideo(
                            video,
                            String.valueOf(pet.getSeq()),
                            cameraId,
                            species,
                            loginUserId
                    );

            return ResponseEntity.ok(result);

        } catch (IllegalArgumentException e) {

            return ResponseEntity.badRequest().body(
                    Map.of(
                            "success", false,
                            "message", e.getMessage()
                    )
            );

        } catch (Exception e) {

            return ResponseEntity.internalServerError().body(
                    Map.of(
                            "success", false,
                            "message", e.getMessage()
                    )
            );
        }
    }

    private String normalizeSpecies(
            String rawSpecies) {

        if (rawSpecies == null
                || rawSpecies.isBlank()) {

            throw new IllegalArgumentException(
                    "반려동물 종 정보가 없습니다."
            );
        }

        String species =
                rawSpecies
                        .trim()
                        .toUpperCase();

        if (species.equals("DOG")
                || species.equals("개")
                || species.equals("강아지")) {

            return "DOG";
        }

        if (species.equals("CAT")
                || species.equals("고양이")) {

            return "CAT";
        }

        throw new IllegalArgumentException(
                "지원하지 않는 반려동물 종입니다: "
                        + rawSpecies
        );
    }
}