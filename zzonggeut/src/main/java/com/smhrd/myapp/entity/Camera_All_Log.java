package com.smhrd.myapp.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "CAMERA_ALL_LOG")
@Getter
@NoArgsConstructor
public class Camera_All_Log 
{
	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "CAM_SEQ", nullable = false)
    private Integer cam_seq;
    
    @Column(name = "PET_SEQ", nullable = false)
    private Integer pet_seq;

    @Column(name = "ACT_VAL")
    private Integer act_val;

    @Column(name = "LOC_TIME")
    private Integer loc_time;

    @Column(name = "M_DISTANCE")
    private Integer m_distance; 
    
    @Column(name = "M_SPEED")
    private Float m_speed;

    @Column(name = "RECORD_DTTM")
    private Float record_dttm; 
}
