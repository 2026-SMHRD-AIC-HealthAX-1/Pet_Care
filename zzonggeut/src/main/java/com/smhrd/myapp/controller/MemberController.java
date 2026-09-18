package com.smhrd.myapp.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import com.smhrd.myapp.entity.UserEntity;

import jakarta.servlet.http.HttpSession;

@Controller
public class MemberController {

    // 1. 회원가입 페이지 띄우기
    @GetMapping("/signup")
    public String signupPage() {
        return "html/signUp"; // templates/html/signUp.html
    }

    // 2. 로그인 페이지 띄우기
    @GetMapping("/login")
    public String loginPage() {
        return "html/login"; // templates/html/login.html
    }

    // 3. 마이페이지 띄우기
    @GetMapping("/mypage")
    public String myPage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login"; // 로그인 안 했으면 로그인 창으로 튕겨내기
        }
        model.addAttribute("loginUser", loginUser);
        return "html/myPage"; 
    }

    // 4. 회원정보 수정 페이지 띄우기
    @GetMapping("/editprofile")
    public String editProfilePage(HttpSession session, Model model) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }
        model.addAttribute("loginUser", loginUser);
        return "html/editProfile"; // templates/html/editProfile.html
    }

    // 5. 비밀번호 변경 페이지 띄우기
    @GetMapping("/changepw")
    public String changePwPage() {
        return "html/changePw"; // templates/html/changePw.html
    }

    // 6. 아이디 찾기 페이지 띄우기
    @GetMapping("/findid")
    public String findIdPage() {
        return "html/findId"; // templates/html/findId.html
    }

    // 7. 비밀번호 찾기 페이지 띄우기
    @GetMapping("/findpw")
    public String findPwPage() {
        return "html/findPw"; // templates/html/findPw.html
    }

    // 8. 회원탈퇴 페이지 띄우기
    @GetMapping("/withdraw")
    public String withdrawPage() {
        return "html/withdraw"; // templates/html/withdraw.html
    }
    
    // 9. 메인 화면
    @GetMapping({"/", "main"})
    public String mainPage() {
        return "html/main"; // templates/html/main.html 파일을 띄움
    }
    
    // 메인 화면
    @GetMapping({"/petmanagement", "petManagement.html"})
    public String petmanagementPage() {
        return "html/petManagement"; // templates/html/petManagement.html 파일을 띄움
    }
    
    // 메인 화면
    @GetMapping({"/roiselect", "roiSelect.html"})
    public String roiselectPage() {
        return "html/roiSelect"; // templates/html/roiSelect.html 파일을 띄움
    }
}