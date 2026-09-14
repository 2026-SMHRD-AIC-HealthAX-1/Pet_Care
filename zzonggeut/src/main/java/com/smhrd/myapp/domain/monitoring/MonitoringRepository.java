package com.smhrd.myapp.domain.monitoring;

import org.springframework.data.jpa.repository.JpaRepository;
import java.time.LocalDateTime;

public interface MonitoringRepository extends JpaRepository<MonitoringEntity, Long> {
}