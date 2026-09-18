package com.smhrd.myapp.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
//import java.util.Optional;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.smhrd.myapp.entity.UserEntity;

public interface UserRepository extends JpaRepository<UserEntity, String> {
    //Optional findByEmail(String email);
	@Modifying
    @Query("DELETE FROM UserEntity u WHERE u.id = :id")
    void deleteUserById(@Param("id") String id);

	Optional<UserEntity> findByNameAndPhone(String name, String phone);
}