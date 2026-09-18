package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "PET_INFO")
@Getter
@NoArgsConstructor
public class PetEntity {

	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "USER_SEQ")
    private Integer user_seq;
    
    @Column(name = "P_NAME", length = 50)
    private String pName;

    @Column(name = "P_GENDER", length = 10)
    private String pGender;

    @Column(name = "P_SPECIES", length = 20)
    private String pSpecies;

    @Column(name = "P_AGE")
    private Integer pAge;

    @Column(name = "P_WEIGHT")
    private Float pWeight;

    @Column(name = "isMule", length = 10)
    private String neutered;
    
    @Column(name = "P_SPEC", length = 200)
    private String pSpec;

    // char 대신 Character 사용으로 null 바인딩 에러 방지
    @Column(name = "isVaccin_1", length = 10)
    private String isVaccin1;

    @Column(name = "isVaccin_2", length = 10)
    private String isVaccin2;
    
    @Column(name = "isVaccin_3", length = 10)
    private String isVaccin3;
    
    @Column(name = "before_Data", length = 500)
    private String beforeData;
}