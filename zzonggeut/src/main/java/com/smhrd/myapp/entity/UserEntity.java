package com.smhrd.myapp.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.AllArgsConstructor;
import lombok.Builder;
import org.springframework.data.domain.Persistable;

@Entity
@Table(name = "`USER`")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserEntity implements Persistable<String>{
	
	// USER 테이블
	
    @Id
//    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "ID", length = 50, nullable = false)
    private String id;

    @Column(name = "PW", length = 100)
    private String pw;

    @Column(name = "NAME", length = 20)
    private String name;

    @Column(name = "PHONE", length = 15)
    private String phone;
    
    //(JPA가 헷갈리지 않고 바로 INSERT 하게 만듦)
    @Override
    public boolean isNew() {
        return true;
    }
    
    private String plan = "basic";
    public String getPlan() {
        return plan != null ? plan : "basic"; // 값이 없으면 기본 'basic' 반환
    }

    public void setPlan(String plan) {
        this.plan = plan;
    }
    
    @Override
    public String getId() {
        return this.id;
    }

    // 프로젝트 다른 곳에서 user_seq라는 이름으로 부를 수도 있으므로 편의 메서드 추가
    public String getUser_seq() {
        return this.id;
    }
    
}