package com.smhrd.myapp.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class ViewController {

    @GetMapping({"/", "/main"})
    public String mainPage() { return "html/main"; }

    @GetMapping("/login")
    public String loginPage() { return "html/login"; }

//    @GetMapping("/join")
//    public String joinPage() { return "join"; } // 파일 안보임

    @GetMapping("/dashboard")
    public String dashboardPage() { return "html/dashboard"; }

//    @GetMapping("/monitoring")
//    public String monitoringPage() { return "monitoring"; }

    @GetMapping("/mypage")
    public String myPage() { return "myPage"; }

//    @GetMapping("/find-id")
//    public String findIdPage() { return "findId"; }
//
//    @GetMapping("/find-pw")
//    public String findPwPage() { return "findPw"; }
}