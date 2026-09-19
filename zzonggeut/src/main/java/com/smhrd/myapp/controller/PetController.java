package com.smhrd.myapp.controller;

import lombok.RequiredArgsConstructor;

import java.util.List;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.PetRepository;

import jakarta.servlet.http.HttpSession;
import jakarta.websocket.Session;

@Controller
public class PetController {

    private final PetRepository repo;

	PetController(PetRepository repo) {
		this.repo = repo;
	}
	
	@GetMapping("/petdelete")
	public String petDelete(@RequestParam("seq") Integer seq, HttpSession session) {
	    UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
	    
	    // 비로그인 상태 처리
	    if (loginUser == null) {
	        return "redirect:/login";
	    }

	    System.out.println("====== 반려동물 삭제 요청 SEQ: " + seq + " ======");

	    // 해당 seq의 반려동물 데이터 삭제
	    repo.deleteById(seq);

	    return "redirect:/pet-management";
	}
	
	@PostMapping("/petupdate")
	public String petUpdate(PetEntity pet, HttpSession session) {
	    UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
	    
	    if (loginUser == null) {
	        return "redirect:/login";
	    }

	    // 보안을 위해 작성자 ID를 로그인한 유저 세션의 ID로 다시 주입
	    pet.setUser_seq(loginUser.getId());

	    // pet 객체 안에 seq(PK)가 포함되어 있으므로 JPA가 자동으로 UPDATE 수행
	    repo.save(pet);

	    System.out.println("====== 반려동물 정보 수정 완료 (SEQ: " + pet.getSeq() + ") ======");

	    return "redirect:/pet-management";
	}
	
	// 1. 페이지 로드 및 반려동물 목록 조회
    @GetMapping({"/pet-management", "/petmanagement"})
    public String petManagementPage(HttpSession session, Model model) {
    	// 1. 세션에서 로그인 객체(UserEntity) 꺼내기
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login"; 
        }

        // 2. UserEntity에서 정수형 시퀀스 번호(PK) 추출
        // ※ UserEntity의 seq 필드 getter 이름에 맞게 호출하세요 (예: getSeq(), getUserSeq() 등)
        String userSeq = loginUser.getId(); 

        // 3. 정수형 userSeq를 파라미터로 넘겨 조회 (repo는 PetRepository여야 함)
        List<PetEntity> petList = repo.findByUser_seq(userSeq);
        
        // 4. 화면으로 데이터 전달
        model.addAttribute("loginUser", loginUser);
        model.addAttribute("petList", petList);

        return "html/petManagement"; // 반려동물 관리 HTML 파일명 (확장자 제외)
    }
    
	@PostMapping("/petinsert") 
	public String petinsert(PetEntity pet, HttpSession session) {
		// 1. 세션에서 "loginUser" 키로 UserEntity 객체 꺼내기
	    UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
	    
	    if (loginUser != null) {
	        // 2. 객체에서 id를 추출하여 PetEntity의 user_seq에 세팅
	        pet.setUser_seq(loginUser.getId());
	        System.out.println("====== 반려동물 등록 성공 ======");
	        System.out.println("주입된 USER_SEQ: " + pet.getUser_seq());
	        System.out.println("등록된 펫 이름: " + pet.getPName());
	    } else {
	        System.out.println("====== 세션 만료: 로그인 정보 없음 ======");
	        return "redirect:/login";
	    }

        repo.save(pet);
        return "redirect:pet-management";
    }
	  
	  
//	@GetMapping
//	public List listPets() { return petService.getAllPets(); }
}