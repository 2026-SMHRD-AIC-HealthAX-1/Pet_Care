package com.smhrd.myapp.controller;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.smhrd.myapp.service.MonitoringService;

import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/monitoring")
public class MonitoringController {

    private final MonitoringService monitoringService;

    @PostMapping("/run-ai")
    public ResponseEntity<?> runAiAnalysis(
            @RequestParam("video") MultipartFile video,
            @RequestParam(defaultValue = "PET-001") String petId,
            @RequestParam(defaultValue = "CAM-001") String cameraId,
            @RequestParam(defaultValue = "DOG") String species) {

        try {
            Map<String, Object> result = monitoringService.analyzeVideo(
                    video,
                    petId,
                    cameraId,
                    species
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
}