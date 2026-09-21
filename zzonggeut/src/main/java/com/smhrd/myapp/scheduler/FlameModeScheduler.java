package com.smhrd.myapp.scheduler;

import com.smhrd.myapp.service.AiModeManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class FlameModeScheduler 
{
	private final AiModeManager aiModeManager;
    private final RestClient restClient = RestClient.create("http://127.0.0.1:8000");

    /**
     * 5초(5000ms)마다 실행
     * flame 모드일 때만 FastAPI에 GET /analyze 요청 전송
     */
    @Scheduled(fixedDelay = 5000)
    public void fetchFlameAnalysis() {
        // flame 모드가 아니면(upload 모드이면) 실행 건너뜀
        if (!aiModeManager.isFlameMode()) {
            return;
        }

        try {
            Map<?, ?> response = restClient.get()
                    .uri("/analyze")
                    .retrieve()
                    .body(Map.class);

            log.info("[Flame 모드] 5초 주기 프레임 분석 결과 수신: {}", response);

            // TODO: 수신 프레임 데이터 처리 및 DB 저장

        } catch (Exception e) {
            log.warn("[Flame 모드 호출 실패] FastAPI 연결 오류: {}", e.getMessage());
        }
    }
}
