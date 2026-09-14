package com.smhrd.myapp.domain.user;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    @Transactional
    public String join(String id, String pw, String name, LocalDateTime birth, char isReceiveAlarm) {
        UserEntity user = UserEntity.builder()
                .id(id)
                .pw(pw)
                .name(name)
                .birth(birth)
                .isReceiveAlarm(isReceiveAlarm)
                .build();
        return userRepository.save(user).getId();
    }
}