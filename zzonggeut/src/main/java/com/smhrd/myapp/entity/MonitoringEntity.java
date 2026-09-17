package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

import com.smhrd.myapp.gita.PetActRecordId;

@Entity
@Table(name = "PET_ACT_RECORD")
@IdClass(PetActRecordId.class)
@Getter
@NoArgsConstructor
public class MonitoringEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "DTTM", nullable=false)
    private LocalDateTime dttm;

    @Column(name = "PET_SEQ", nullable=false)
    private Integer petSeq;

    @Column(name = "ACT_NAME", length = 10)
    private String actName;

    @Column(name = "ACT_TIME")
    private Integer actTime;

    public MonitoringEntity(LocalDateTime dttm, Integer petSeq, String actName, Integer actTime) {
        this.dttm = dttm;
        this.petSeq = petSeq;
        this.actName = actName;
        this.actTime = actTime;
    }
}