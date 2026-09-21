package com.smhrd.myapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import com.smhrd.myapp.entity.Camera_Roi_Info;

@Repository
public interface RoiInfoRepository extends JpaRepository<Camera_Roi_Info, String>
{

}
