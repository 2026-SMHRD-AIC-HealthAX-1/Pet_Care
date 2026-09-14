package com.smhrd.myapp.domain.monitoring;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MonitoringService {
    private final MonitoringRepository monitoringRepository;
}