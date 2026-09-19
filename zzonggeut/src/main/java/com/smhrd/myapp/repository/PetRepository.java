package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import org.springframework.stereotype.Repository;

import com.smhrd.myapp.entity.PetEntity;

@Repository
public interface PetRepository extends JpaRepository<PetEntity, Integer> {
	// 특정 유저(USER_SEQ)의 반려동물 목록 조회
	@Query("SELECT p FROM PetEntity p WHERE p.user_seq = :userSeq")
    List<PetEntity> findByUser_seq(@Param("userSeq") String userSeq);
	

}