package com.smhrd.myapp.repository;

import com.smhrd.myapp.entity.PetActRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;

@Repository
public interface PetActRecordRepository extends JpaRepository<PetActRecord, LocalDateTime>
{

}
