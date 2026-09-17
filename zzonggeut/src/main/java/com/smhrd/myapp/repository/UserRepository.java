package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
//import java.util.Optional;

import com.smhrd.myapp.entity.UserEntity;

public interface UserRepository extends JpaRepository<UserEntity, String> {
    //Optional findByEmail(String email);
}