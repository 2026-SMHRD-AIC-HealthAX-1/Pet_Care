package com.smhrd.myapp.repository;

import com.smhrd.myapp.entity.PetActRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public interface PetActRecordRepository extends JpaRepository<PetActRecord, LocalDateTime>
{
	// 🌟 오늘 날짜의 특정 유저 + 펫 체류 기록 조회
    @Query("SELECT r FROM PetActRecord r " +
           "WHERE r.userSeq = :userSeq " +
           "  AND r.petSeq = :petSeq " +
           "  AND r.dttm >= :startOfDay AND r.dttm <= :endOfDay " +
           "ORDER BY r.dttm DESC")
    List<PetActRecord> findTodayRecords(
            @Param("userSeq") String userSeq,
            @Param("petSeq") Integer petSeq,
            @Param("startOfDay") LocalDateTime startOfDay,
            @Param("endOfDay") LocalDateTime endOfDay
    );
}
