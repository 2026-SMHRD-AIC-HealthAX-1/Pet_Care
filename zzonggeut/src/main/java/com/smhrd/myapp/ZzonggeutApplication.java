package com.smhrd.myapp;

import org.springframework.boot.SpringApplication;
//import org.mybatis.spring.annotation.MapperScan; // 임포트 추가
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling; // 추가

@EnableScheduling // 추가
@SpringBootApplication
//@MapperScan("com.smhrd.myapp.mapper") // <- 이 한 줄 추가
public class ZzonggeutApplication {

	public static void main(String[] args) {
		SpringApplication.run(ZzonggeutApplication.class, args);
	}

}
