package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
//import java.util.List;

import com.smhrd.myapp.entity.PetEntity;

public interface PetRepository extends JpaRepository<PetEntity, Integer> {
	//List findByUserId(Long userId);
}