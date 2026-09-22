package com.smhrd.myapp.controller;

import java.util.ArrayList;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseBody;

import com.smhrd.myapp.dto.RoiRequestDto;
import com.smhrd.myapp.entity.Camera_Roi_Info;
import com.smhrd.myapp.repository.RoiInfoRepository;



@Controller
public class RoiInfoController 
{
	private final RoiInfoRepository repo;
	
	public RoiInfoController(RoiInfoRepository repo) {
		this.repo = repo;
	}
	
	@PostMapping("/roidelete")
	@ResponseBody // 🌟 뷰(HTML)를 찾지 않고 성공 응답 본문 리턴
	public ResponseEntity<String> roidelete() 
	{ 
		repo.deleteAllInBatch();
	  
		return ResponseEntity.ok("SUCCESS");
	  
		//return "redirect:/roiselect"; 
	}
	
	// ==========================================
    // DB 데이터 조회 API (JSON 반환)
    // ==========================================
    @GetMapping("/roiget")
    @ResponseBody
    public List<Camera_Roi_Info> roiget() {
        return repo.findAll();
    }
    
	@PostMapping("/roiinsert") 
	@ResponseBody
	public ResponseEntity<String> roiinsert(@RequestBody RoiRequestDto dto) 
	{ 
		try {
	        if (dto.getRois() == null || dto.getRois().isEmpty()) {
	            return ResponseEntity.badRequest().body("저장할 ROI 데이터가 없습니다.");
	        }

	        // ==========================================
            // 3. 기존 테이블 데이터 전체 삭제 (TRUNCATE/단일 DELETE 실행)
            // ==========================================
            repo.deleteAllInBatch();
            
	        Integer camSeq = 0; // 사용하는 카메라 시퀀스
	        List<Camera_Roi_Info> entityList = new ArrayList<>();

	        for (RoiRequestDto.RoiItemDto item : dto.getRois()) {
	        	Camera_Roi_Info entity = new Camera_Roi_Info(
	        	        item.getId(), // 변환 없이 그대로 주입
	        	        camSeq,
	        	        item.getName(),
	        	        item.getX(),
	        	        item.getWidth(),
	        	        item.getY(),
	        	        item.getHeight()
	        	    );

	            entityList.add(entity);
	        }

	        // 3. DB 일괄 저장 실행
	        repo.saveAll(entityList);

	        return ResponseEntity.ok("success");
	    } catch (Exception e) {
	        e.printStackTrace();
	        return ResponseEntity.status(500).body("서버 에러: " + e.getMessage());
	    }
	}
}
