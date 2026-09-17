package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.smhrd.myapp.entity.AnalysisEntity;

public interface AnalysisRepository extends JpaRepository<AnalysisEntity, Long> {
}