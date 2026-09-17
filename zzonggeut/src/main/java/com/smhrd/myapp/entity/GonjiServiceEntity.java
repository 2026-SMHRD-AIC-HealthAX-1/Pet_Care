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
@Table(name = "GONGJI_SERVICE")
@Getter
@NoArgsConstructor
public class GonjiServiceEntity 
{
	@Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "SEQ", nullable = false)
    private Integer seq;

    @Column(name = "GUBUN", length = 5)
    private String gubun;
    
    @Column(name = "TITLE", length = 100)
    private String title;

    @Column(name = "CONTENT", length = 200)
    private String content;

}
