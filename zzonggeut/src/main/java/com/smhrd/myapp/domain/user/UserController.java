package com.smhrd.myapp.domain.user;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping("/login")
    public String loginPage() {
        return "login"; // templates/login.html
    }

    @GetMapping("/join")
    public String joinPage() {
        return "join"; // templates/join.html
    }

    @PostMapping("/join")
    public String join(@RequestParam String email, 
                       @RequestParam String password, 
                       @RequestParam String name) {
        userService.join(email, password, name);
        return "redirect:/login";
    }
}