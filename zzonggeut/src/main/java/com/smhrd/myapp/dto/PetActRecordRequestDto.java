package com.smhrd.myapp.dto;

import lombok.Data;

@Data
public class PetActRecordRequestDto 
{
	private Integer petSeq;
    private String userSeq;
    private String roiName;
    private Integer continueTime;
    private Float stopRatio;
}
