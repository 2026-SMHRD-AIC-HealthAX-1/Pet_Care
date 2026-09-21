package com.smhrd.myapp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling; // 추가

@EnableScheduling // 추가
@SpringBootApplication
public class ZzonggeutApplication {

	public static void main(String[] args) {
		SpringApplication.run(ZzonggeutApplication.class, args);
	}

}
