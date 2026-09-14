package com.smhrd.myapp.domain.monitoring;

import org.springframework.data.jpa.repository.JpaRepository;

public interface MonitoringRepository extends JpaRepository<MonitoringEntity, Long> {
}