package com.smhrd.myapp.dto;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import java.util.Map;

@Getter
@Setter
@ToString
public class PetAnalysisResultDto 
{
	private String mode;
    private String analyzedAt;
    private Map<String, Object> data; // PetBehaviorAnalyzer 반환 dict 매핑
}
