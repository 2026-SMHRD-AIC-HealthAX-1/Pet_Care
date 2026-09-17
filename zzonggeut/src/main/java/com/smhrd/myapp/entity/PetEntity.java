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

    @Column(name = "USER_SEQ", nullable = false)
    private Integer user_seq;
    
    @Column(name = "P_NAME", length = 5, nullable = false)
    private String pName;

    @Column(name = "P_GENDER", length = 3, nullable = false)
    private char pGender;

    @Column(name = "P_SPECIES", length = 10, nullable = false)
    private String pSpecies;

    @Column(name = "P_AGE", nullable = false)
    private Integer pAge; // TINYINT 매핑

    @Column(name = "P_WEIGHT", nullable = false)
    private Integer pWeight;

    @Column(name = "isMule", length = 1, nullable = false)
    private char isMule;
    
    @Column(name = "P_SPEC", length = 200)
    private String pSpec;

    @Column(name = "isVaccin_1", length = 1, nullable = false)
    private char isVaccin_1;

    @Column(name = "isVaccin_2", length = 1, nullable = false)
    private char isVaccin_2;
    
    @Column(name = "isVaccin_3", length = 1, nullable = false)
    private char isVaccin_3;
    
    public PetEntity(String pName, char pGender, String pSpecies, Integer pAge, Integer pWeight,
                     String pSpec, char isMule, char isVaccin_1, char isVaccin_2, char isVaccin_3) {
        this.pName = pName;
        this.pGender = pGender;
        this.pSpecies = pSpecies;
        this.pAge = pAge;
        this.pWeight = pWeight;
        this.pSpec = pSpec;
        this.isMule = isMule;
        this.isVaccin_1 = isVaccin_1;
        this.isVaccin_2 = isVaccin_2;
        this.isVaccin_3 = isVaccin_3;

    }
}