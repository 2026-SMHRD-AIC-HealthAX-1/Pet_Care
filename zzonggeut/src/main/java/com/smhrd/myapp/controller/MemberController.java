package com.smhrd.myapp.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;

import com.smhrd.myapp.entity.UserEntity;

import jakarta.servlet.http.HttpSession;

@Controller
public class MemberController {

    // --- 1. 일반 페이지 매핑 (구 PageController 역할 통합) ---

    @GetMapping("/")
    public String main() {
        return "html/mainBefore"; // 로그인 전 메인
    }

    @GetMapping("/serviceIntro")
    public String serviceIntro(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }
        return "html/serviceIntro";
    }

    @GetMapping("/servicePrice")
    public String servicePrice(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }
        return "html/servicePrice";
    }

    @GetMapping("/notice")
    public String notice() {
        return "html/notice";
    }
    
    // ❌ 중복되었던 단순 @GetMapping("/contact") 은 삭제 완료!

    // --- 2. 회원 및 서비스 가입/이용 페이지 매핑 ---

    @GetMapping("/signup")
    public String signupPage() {
        return "html/signUp";
    }

    @GetMapping("/login")
    public String loginPage() {
        return "html/login";
    }

 // 서비스 가입 페이지 띄우기 (GET)
    @GetMapping("/service-signup")
    public String serviceSignupPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        
        // 필요시 반려동물 목록 조회 후 model.addAttribute("petList", petList); 추가
        
        return "html/serviceSignUp"; // templates/html/serviceSignUp.html
    }

    // 서비스 가입 처리 (POST)
    @PostMapping("/service-signup")
    public String serviceSignupProcess(HttpSession session /*, 요청 파라미터들 */) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        
        // 가입 로직 처리 구현
        
        return "redirect:/main";
    }

    @GetMapping("/mypage")
    public String myPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/myPage"; 
    }

    @GetMapping("/editprofile")
    public String editProfilePage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/editProfile";
    }

    @GetMapping("/changepw")
    public String changePwPage() {
        return "html/changePw";
    }

    @GetMapping("/findid")
    public String findIdPage() {
        return "html/findId";
    }

    @GetMapping("/findpw")
    public String findPwPage() {
        return "html/findPw";
    }

    @GetMapping("/withdraw")
    public String withdrawPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/withdraw"; // templates/html/withdraw.html
    }
    
    // 로그인 후 메인 화면
    @GetMapping("/main")
    public String mainPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        
         // 🧪 테스트용: 유저의 플랜이 없을 경우 기본 'standard' 혹은 'basic'으로 지정 가능
         if (loginUser.getPlan() == null) {
             loginUser.setPlan("standard"); // "basic", "standard", "premium" 변경하며 테스트
         }
        
        model.addAttribute("loginUser", loginUser);
        return "html/mainAfter";
    }
    
    @GetMapping("/inquiry")
    public String inquiryPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/1on1Inquiry"; 
    }
    
    // ✅ 세션 검증이 포함된 문의하기 페이지 매핑
    @GetMapping("/contact")
    public String contactPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/contact";
    }
    
    @GetMapping("/dashboard")
    public String dashboardPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/dashboard";
    }
    
    // 자주 묻는 질문(FAQ) 페이지 띄우기
    @GetMapping("/fnq")
    public String fnqPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }
        return "html/fnq"; 
    }
    
	/*
	 * @GetMapping("/pet-management") public String petManagementPage(HttpSession
	 * session, Model model) { UserEntity loginUser = (UserEntity)
	 * session.getAttribute("loginUser"); if (loginUser == null) { return
	 * "redirect:/login"; } model.addAttribute("loginUser", loginUser); return
	 * "html/petManagement"; // templates/html/petManagement.html }
	 */
    
    @GetMapping("/privacy")
    public String privacyPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }
        return "html/privacy"; // templates/html/privacy.html
    }
    
    @GetMapping("/report")
    public String reportPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/report"; // templates/html/report.html
    }
    
    @GetMapping({"/roiselect", "roi-select"})
    public String roiSelectPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/roiSelect"; // templates/html/roiSelect.html
    }
    
    @GetMapping("/use")
    public String usePage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }
        return "html/use"; // templates/html/use.html
    }
}