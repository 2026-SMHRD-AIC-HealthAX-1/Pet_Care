package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.smhrd.myapp.entity.MonitoringEntity;
import com.smhrd.myapp.gita.PetActRecordId;


public interface MonitoringRepository extends JpaRepository<MonitoringEntity, PetActRecordId> {
}