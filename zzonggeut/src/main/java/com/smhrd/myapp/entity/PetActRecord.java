package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

@Entity
@Table(name = "PET_ACT_RECORD")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PetActRecord 
{
	@Id
    @Column(name = "DTTM", nullable = false)
    private LocalDateTime dttm; // PK: 일시

    @Column(name = "PET_SEQ")
    private Integer petSeq;

    @Column(name = "USER_SEQ", length = 50)
    private String userSeq;

    @Column(name = "ROI_NAME", length = 20)
    private String roiName;

    @Column(name = "CONTINUE_TIME")
    private Integer continueTime;

    @Column(name = "STOP_RATIO")
    private Float stopRatio; // 체류 비율
}
