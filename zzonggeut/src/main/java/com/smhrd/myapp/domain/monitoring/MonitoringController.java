package com.smhrd.myapp.domain.monitoring;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
public class MonitoringController {
    private final MonitoringService monitoringService;
}