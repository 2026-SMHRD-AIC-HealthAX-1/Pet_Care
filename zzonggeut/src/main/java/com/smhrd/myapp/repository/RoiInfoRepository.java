package com.smhrd.myapp.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import com.smhrd.myapp.entity.Camera_Roi_Info;

@Repository
public interface RoiInfoRepository extends JpaRepository<Camera_Roi_Info, String> {

    // 특정 카메라의 ROI만 조회
    @Query("""
        SELECT r
        FROM Camera_Roi_Info r
        WHERE r.cam_seq = :camSeq
        ORDER BY r.seq ASC
    """)
    List<Camera_Roi_Info> findAllByCamSeq(@Param("camSeq") Integer camSeq);

    // 특정 카메라의 ROI만 삭제
    @Modifying
    @Transactional
    @Query("""
        DELETE FROM Camera_Roi_Info r
        WHERE r.cam_seq = :camSeq
    """)
    int deleteAllByCamSeq(@Param("camSeq") Integer camSeq);
}