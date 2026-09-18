package com.smhrd.myapp.controller;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ai")
public class AiAnalysisResultController {

    @PostMapping("/analysis-results")
    public ResponseEntity<Map<String, Object>> receiveAnalysisResult(
            @RequestBody Map<String, Object> result) {

        String analysisId = String.valueOf(
                result.getOrDefault("analysis_id", "")
        );

        String schemaVersion = String.valueOf(
                result.getOrDefault("schema_version", "")
        );

        String analysisStatus = String.valueOf(
                result.getOrDefault("analysis_status", "")
        );

        System.out.println(
                "[AI RESULT RECEIVED] "
                + "analysis_id=" + analysisId
                + ", schema_version=" + schemaVersion
                + ", analysis_status=" + analysisStatus
        );

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("analysis_id", analysisId);
        response.put("message", "AI analysis result received successfully.");

        return ResponseEntity.ok(response);
    }
}
