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
@Table(name = "CAMERA_INFO")
@Getter
@NoArgsConstructor
public class Camera_Info 
{
	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "USER_SEQ", nullable = false)
    private Integer user_seq;
    
    @Column(name = "CAMERA_NUM", nullable = false)
    private Integer camera_num;

    @Column(name = "CAMERA_NAME", length = 20, nullable = false)
    private String camera_name;
}
