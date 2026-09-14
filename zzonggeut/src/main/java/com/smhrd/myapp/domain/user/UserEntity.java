package com.smhrd.myapp.domain.user;

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
    @Id
    @Column(name = "ID", length = 10, nullable = false)
    private String id;

    @Column(name = "PW", length = 10)
    private String pw;

    @Column(name = "NAME", length = 10)
    private String name;

    @Column(name = "BIRTH")
    private LocalDateTime birth;

    @Column(name = "isReceiveAlarm", length = 1)
    private char isReceiveAlarm;
}