package com.smhrd.myapp.service;

import org.springframework.stereotype.Component;

@Component
public class AiModeManager 
{
	// 초기 기본값
    private volatile String currentMode = "upload";

    public void setMode(String mode) {
        this.currentMode = mode;
    }

    public String getMode() {
        return this.currentMode;
    }

    public boolean isFlameMode() {
        return "flame".equalsIgnoreCase(this.currentMode);
    }
}
