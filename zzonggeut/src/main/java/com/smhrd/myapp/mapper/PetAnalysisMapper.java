package com.smhrd.myapp.mapper;

import java.util.Map;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface PetAnalysisMapper 
{
    void insertBehaviorMap(Map<String, Object> paramMap);

    Map<String, Object> selectLatestBehaviorMap();
}