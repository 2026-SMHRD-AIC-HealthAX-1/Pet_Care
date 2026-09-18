package com.smhrd.myapp.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.repository.UserRepository;

import java.time.LocalDateTime;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    @Transactional
    public String join(String id, String pw, String name, String phone) {
        UserEntity user = UserEntity.builder()
                .id(id)
                .pw(pw)
                .name(name)
                .phone(phone)
                .build();
        return userRepository.save(user).getId();
    }
    
    public UserEntity login(String id, String pw) {
        // 1. 아이디로 회원 조회
        Optional<UserEntity> optionalUser = userRepository.findById(id);
        
        if (optionalUser.isPresent()) {
            UserEntity user = optionalUser.get();
            // 2. 입력한 비밀번호와 DB의 비밀번호가 일치하는지 확인
            if (user.getPw().equals(pw)) {
                return user; // 로그인 성공
            }
        }
        return null; // 로그인 실패
    }
    
 // 회원 정보 수정 처리 메서드
    @Transactional
    public void updateUser(String id, String name, String phone) {
        // 1. DB에서 해당 아이디로 유저를 찾음
        UserEntity user = userRepository.findById(id).orElse(null);
        
        // 2. 유저가 존재하면 이름과 전화번호를 변경하고 저장(Update)
        if (user != null) {
            user.setName(name);
            user.setPhone(phone);
            userRepository.save(user); // JpaRepository가 제공하는 save는 기존에 아이디가 있으면 수정(Update)을 해줍니다!
        }
    }
    
 // 아이디로 유저 정보 조회
    public UserEntity findId(String id) { // 또는 findById
        return userRepository.findById(id).orElse(null);
    }
    
 // 비밀번호 변경 처리 메서드
    @Transactional
    public boolean updatePassword(String id, String currentPassword, String newPassword) {
        UserEntity user = userRepository.findById(id).orElse(null);
        
        if (user == null) {
            return false;
        }

        // 1. 현재 비밀번호가 틀린 경우
        if (!user.getPw().equals(currentPassword)) {
            return false;
        }

        // 2. [추가] 기존 비밀번호와 새 비밀번호가 똑같은 경우!
        if (currentPassword.equals(newPassword)) {
            return false; 
        }

        // 3. 정상 변경
        user.setPw(newPassword);
        userRepository.save(user);
        return true;
    }
    
 // 회원탈퇴 처리 메서드
 // 회원탈퇴 처리 메서드
    @Transactional
    public boolean withdrawUser(String id, String password) {
        System.out.println(">>> withdrawUser 메서드 진입! 아이디: " + id);
        
        UserEntity user = userRepository.findById(id).orElse(null);
        
        if (user == null) {
            System.out.println(">>> 실패: 해당 아이디의 유저를 찾을 수 없음");
            return false;
        }

        System.out.println(">>> 사용자가 입력한 비밀번호: [" + password + "]");
        System.out.println(">>> DB에 저장된 실제 비밀번호: [" + user.getPw() + "]");

        // 비밀번호 검증
        if (!user.getPw().equals(password)) {
            System.out.println(">>> 실패: 비밀번호 불일치!!");
            return false; 
        }

        System.out.println(">>> 비밀번호 일치! ID 조건으로 직접 삭제 실행...");
        
        // 💡 JPA 내장 delete 대신 우리가 만든 PK 조건 삭제 쿼리 실행!
        userRepository.deleteUserById(id);
        userRepository.flush(); 
        
        System.out.println(">>> 직접 삭제 및 플러시 완료!");
        return true;
    }
    
 // 이름과 전화번호로 유저를 찾아 아이디 반환
    public String findUserByNamerAndPhone(String name, String phone) {
        UserEntity user = userRepository.findByNameAndPhone(name, phone).orElse(null);
        if (user != null) {
            return user.getId();
        }
        return null;
    }
    
 // 비밀번호 재설정 (결과에 따라 상태 문자열 반환)
    @Transactional
    public String resetPassword(String id, String phone, String newPassword) {
        UserEntity user = userRepository.findById(id).orElse(null);

        // 1. 유저가 없거나 전화번호가 틀린 경우
        if (user == null || !user.getPhone().equals(phone)) {
            return "NOT_FOUND";
        }

        // 2. 💡 기존 비밀번호와 새 비밀번호가 똑같은 경우
        if (user.getPw().equals(newPassword)) {
            return "SAME_PASSWORD";
        }

        // 3. 정상 변경
        user.setPw(newPassword);
        userRepository.save(user);
        userRepository.flush();

        return "SUCCESS";
    }
}