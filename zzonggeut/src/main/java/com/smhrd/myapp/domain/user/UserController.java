package com.smhrd.myapp.domain.user;

import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDateTime;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/users")
public class UserController {
    private final UserService userService;

    @PostMapping("/join")
    public String join(
            @RequestParam String id,
            @RequestParam String pw,
            @RequestParam String name,
            @RequestParam @DateTimeFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss") LocalDateTime birth,
            @RequestParam char isReceiveAlarm
    ) {
        return userService.join(id, pw, name, birth, isReceiveAlarm);
    }
}