package com.smhrd.myapp.domain.pet;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface PetRepository extends JpaRepository<PetEntity, Integer> {
	List findByUserId(Long userId);
}