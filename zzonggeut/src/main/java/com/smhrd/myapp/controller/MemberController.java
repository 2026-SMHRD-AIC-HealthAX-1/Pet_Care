package com.smhrd.myapp.controller;

import java.util.List;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.PetRepository;

import jakarta.servlet.http.HttpSession;

@Controller
public class MemberController {

    private final PetRepository petRepository;

    public MemberController(PetRepository petRepository) {
        this.petRepository = petRepository;
    }

    // --- 1. 일반 페이지 매핑 ---

// 로그인 전 메인 화면으로 들어갔을 때 로그인 여부를 판단해서 로그인 전이면 before, 후면 after를 띄움
    @GetMapping("/")
    public String main(HttpSession session) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            return "redirect:/main";
        }

        return "html/mainBefore";
    }

    @GetMapping("/serviceIntro")
    public String serviceIntro(HttpSession session, Model model) {
        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }

        return "html/serviceIntro";
    }

    @GetMapping("/servicePrice")
    public String servicePrice(HttpSession session, Model model) {
        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            model.addAttribute("loginUser", loginUser);
        }

        return "html/servicePrice";
    }

    @GetMapping("/notice")
    public String notice() {
        return "html/notice";
    }

    // --- 2. 회원 및 서비스 가입/이용 페이지 매핑 ---

    @GetMapping("/signup")
    public String signupPage() {
        return "html/signUp";
    }

    @GetMapping("/login")
    public String loginPage() {
        return "html/login";
    }

    @GetMapping("/service-signup")
    public String serviceSignupPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/serviceSignUp";
    }

    @PostMapping("/service-signup")
    public String serviceSignupProcess(
            HttpSession session) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        return "redirect:/main";
    }

    @GetMapping("/mypage")
    public String myPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/myPage";
    }

    @GetMapping("/editprofile")
    public String editProfilePage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

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
    public String withdrawPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/withdraw";
    }

    // 로그인 후 메인 화면
    @GetMapping("/main")
    public String mainPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        if (loginUser.getPlan() == null) {
            loginUser.setPlan("standard");
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/mainAfter";
    }

    @GetMapping("/inquiry")
    public String inquiryPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/1on1Inquiry";
    }

    @GetMapping("/contact")
    public String contactPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/contact";
    }

    // ==========================================
    // Dashboard
    // 로그인 사용자 + 해당 사용자의 PET 목록 전달
    // ==========================================
    @GetMapping("/dashboard")
    public String dashboardPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        List<PetEntity> petList =
                petRepository.findByUser_seq(
                        loginUser.getId()
                );

        model.addAttribute(
                "loginUser",
                loginUser
        );

        model.addAttribute(
                "petList",
                petList
        );

        return "html/dashboard";
    }

    @GetMapping("/fnq")
    public String fnqPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            model.addAttribute(
                    "loginUser",
                    loginUser
            );
        }

        return "html/fnq";
    }

    @GetMapping("/privacy")
    public String privacyPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            model.addAttribute(
                    "loginUser",
                    loginUser
            );
        }

        return "html/privacy";
    }

    @GetMapping("/report")
    public String reportPage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        model.addAttribute(
                "loginUser",
                loginUser
        );

        return "html/report";
    }

    @GetMapping({"/roiselect", "/roi-select"})
    public String roiSelectPage(HttpSession session, Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser == null) {
            return "redirect:/login";
        }

        List<PetEntity> petList =
                petRepository.findByUser_seq(loginUser.getId());

        model.addAttribute("loginUser", loginUser);
        model.addAttribute("petList", petList);

        return "html/roiSelect";
    }

    @GetMapping("/use")
    public String usePage(
            HttpSession session,
            Model model) {

        UserEntity loginUser =
                (UserEntity) session.getAttribute("loginUser");

        if (loginUser != null) {
            model.addAttribute(
                    "loginUser",
                    loginUser
            );
        }

        return "html/use";
    }
}