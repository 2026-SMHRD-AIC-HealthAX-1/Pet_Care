package com.smhrd.myapp.mapper;

import java.util.Map;
import org.apache.ibatis.annotations.Mapper; // <- 이 경로여야 합니다!

@Mapper
public interface PetAnalysisMapper 
{
	void insertBehaviorMap(Map<String, Object> paramMap);
}
