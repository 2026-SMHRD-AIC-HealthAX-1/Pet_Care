package com.smhrd.myapp.domain.monitoring;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "PET_ACT_RECORD")
@IdClass(PetActRecordId.class)
@Getter
@NoArgsConstructor
public class MonitoringEntity {

    @Id
    @Column(name = "DTTM")
    private LocalDateTime dttm;

    @Id
    @Column(name = "PET_SEQ")
    private Integer petSeq;

    @Column(name = "ACT_NAME", length = 10)
    String actName;

    @Column(name = "ACT_TIME")
    private Integer actTime;

    public MonitoringEntity(LocalDateTime dttm, Integer petSeq, String actName, Integer actTime) {
        this.dttm = dttm;
        this.petSeq = petSeq;
        this.actName = actName;
        this.actTime = actTime;
    }
}