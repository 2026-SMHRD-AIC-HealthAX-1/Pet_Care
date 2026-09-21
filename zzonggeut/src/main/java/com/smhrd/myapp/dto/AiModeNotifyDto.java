package com.smhrd.myapp.dto;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

@Getter
@Setter
@ToString
public class AiModeNotifyDto 
{
	private String mode;      // "flame" 또는 "upload"
    private String timestamp; // 전송 일시
}
