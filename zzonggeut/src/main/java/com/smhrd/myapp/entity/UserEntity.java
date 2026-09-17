package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import java.time.LocalDateTime;

@Entity
@Table(name = "USER")
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserEntity {
	
	// USER 테이블
	
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "ID", length = 10, nullable = false)
    private String id;

    @Column(name = "PW", length = 10)
    private String pw;

    @Column(name = "NAME", length = 10)
    private String name;

    @Column(name = "BIRTH")
    private LocalDateTime birth;
}