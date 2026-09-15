package com.smhrd.myapp.domain.analysis;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
public class AnalysisController {
    private final AnalysisService analysisService;
}