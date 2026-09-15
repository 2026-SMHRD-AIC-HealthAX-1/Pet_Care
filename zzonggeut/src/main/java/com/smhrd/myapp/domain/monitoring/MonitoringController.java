package com.smhrd.myapp.domain.monitoring;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/monitoring")
public class MonitoringController {
    private final MonitoringService monitoringService;

    @PostMapping("/run-ai")
    public String runAiAnalysis() {
        return monitoringService.executePythonPipeline();
    }
}