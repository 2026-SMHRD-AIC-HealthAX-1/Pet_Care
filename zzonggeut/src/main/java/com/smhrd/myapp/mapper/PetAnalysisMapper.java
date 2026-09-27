package com.smhrd.myapp.mapper;

import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface PetAnalysisMapper {

    void insertBehaviorMap(
            Map<String, Object> paramMap
    );


    // 로그인 사용자의 가장 최근 분석 결과
    Map<String, Object> selectLatestBehaviorMapByUser(
            @Param("userSeq")
            String userSeq
    );


    // 로그인 사용자 + 선택한 PET의 가장 최근 분석 결과
    Map<String, Object> selectLatestBehaviorMapByUserAndPet(
            @Param("userSeq")
            String userSeq,

            @Param("petId")
            Integer petId
    );
}