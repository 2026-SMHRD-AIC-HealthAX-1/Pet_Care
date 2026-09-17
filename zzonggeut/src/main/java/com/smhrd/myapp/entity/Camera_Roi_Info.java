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
@Table(name = "CAMERA_ROI_INFO")
@Getter
@NoArgsConstructor
public class Camera_Roi_Info 
{
	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "CAM_SEQ", nullable = false)
    private Integer cam_seq;
    
    @Column(name = "ROI_NAME", length = 10, nullable = false)
    private String roi_name;

    @Column(name = "X_START", nullable = false)
    private Integer x_start;

    @Column(name = "X_END", nullable = false)
    private Integer x_end;

    @Column(name = "Y_START", nullable = false)
    private Integer y_start;

    @Column(name = "Y_END", nullable = false)
    private Integer y_end;
}
