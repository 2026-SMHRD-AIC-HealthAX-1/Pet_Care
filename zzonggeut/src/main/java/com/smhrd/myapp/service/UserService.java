package com.smhrd.myapp.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.UserRepository;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    @Transactional
    public String join(String id, String pw, String name, LocalDateTime birth) {
        UserEntity user = UserEntity.builder()
                .id(id)
                .pw(pw)
                .name(name)
                .birth(birth)
                .build();
        return userRepository.save(user).getId();
    }
}