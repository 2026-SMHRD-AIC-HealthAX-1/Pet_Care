package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "PET_ACT_CHANGE")
@Getter
@NoArgsConstructor
public class AnalysisEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "PET_SEQ", nullable = false)
    private Integer petSeq;

    @Column(name = "DTTM", nullable = false)
    private LocalDateTime dttm;

    @Column(name = "GIJUN_ACT_TIME")
    private Integer gijunActTime;

    @Column(name = "CHANGE_ACT_TIME")
    private Integer changeActTime;

    @Column(name = "GIJUN_ACT_LEVEL")
    private Integer gijunActLevel;

    @Column(name = "CHANGE_ACT_LEVEL")
    private Integer changeActLevel;
}