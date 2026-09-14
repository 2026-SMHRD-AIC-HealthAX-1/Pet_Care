package com.smhrd.myapp.domain.pet;

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
    @Column(name = "SEQ")
    private Integer seq;

    @Column(name = "P_NAME", length = 5, nullable = false)
    private String pName;

    @Column(name = "P_GENDER", length = 1, nullable = false)
    private char pGender;

    @Column(name = "P_SPECIES", length = 10, nullable = false)
    private String pSpecies;

    @Column(name = "P_AGE", nullable = false)
    private Byte pAge; // TINYINT 매핑

    @Column(name = "P_WEIGHT", nullable = false)
    private Integer pWeight;

    @Column(name = "P_SPEC", length = 200, nullable = false)
    private String pSpec;

    @Column(name = "isMule", length = 1, nullable = false)
    private char isMule;

    @Column(name = "isVaccin", length = 1, nullable = false)
    private char isVaccin;

    @Column(name = "P_BEFORE_INFO", length = 200, nullable = false)
    private String pBeforeInfo;

    public PetEntity(String pName, char pGender, String pSpecies, Byte pAge, Integer pWeight,
                     String pSpec, char isMule, char isVaccin, String pBeforeInfo) {
        this.pName = pName;
        this.pGender = pGender;
        this.pSpecies = pSpecies;
        this.pAge = pAge;
        this.pWeight = pWeight;
        this.pSpec = pSpec;
        this.isMule = isMule;
        this.isVaccin = isVaccin;
        this.pBeforeInfo = pBeforeInfo;
    }
}