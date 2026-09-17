package com.smhrd.myapp.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "PET_LOC")
@Getter
@NoArgsConstructor
public class PetLocEntity 
{
	// PetLoc 테이블
	
	 @Id
	 @GeneratedValue(strategy = GenerationType.IDENTITY)
	 @Column(name = "DTTM", nullable = false)
	 private LocalDateTime dttm;

	 @Column(name = "PET_SEQ", nullable = false)
	 private Integer pet_seq;

	 @Column(name = "PRODUCT_NAME", length = 20)
	 private String product_name;

	 @Column(name = "ACT_TIME")
	 private Integer act_time;
	 
	 @Column(name = "ACT_LEVEL")
	 private Integer act_level;
}
