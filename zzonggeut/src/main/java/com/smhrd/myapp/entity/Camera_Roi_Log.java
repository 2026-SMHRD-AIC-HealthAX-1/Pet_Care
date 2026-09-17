package com.smhrd.myapp.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import java.time.LocalDateTime;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "CAMERA_ROI_LOG")
@Getter
@NoArgsConstructor
public class Camera_Roi_Log 
{
	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "ROI_SEQ", nullable = false)
    private Integer roi_seq;
    
    @Column(name = "PET_SEQ", nullable = false)
    private Integer pet_seq;

    @Column(name = "ST_DTTM")
    private LocalDateTime st_dttm;

    @Column(name = "ED_DTTM")
    private LocalDateTime ed_dttm;

    @Column(name = "C_TIME")
    private Integer c_time ; 

}
