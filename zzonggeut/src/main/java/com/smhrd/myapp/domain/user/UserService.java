package com.smhrd.myapp.domain.user;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    @Transactional
    public Long join(String email, String password, String name) {
        UserEntity user = UserEntity.builder()
                .email(email)
                .password(password)
                .name(name)
                .build();
        return userRepository.save(user).getId();
    }
}