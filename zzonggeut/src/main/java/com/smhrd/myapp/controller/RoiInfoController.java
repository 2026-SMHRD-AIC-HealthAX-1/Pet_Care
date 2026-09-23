package com.smhrd.myapp.controller;

import java.util.ArrayList;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseBody;

import com.smhrd.myapp.dto.RoiRequestDto;
import com.smhrd.myapp.entity.Camera_Roi_Info;
import com.smhrd.myapp.repository.RoiInfoRepository;

@Controller
public class RoiInfoController {

    /*
     * 현재 CAMERA_INFO와 로그인 USER 연결 구조가 아직 확정되지 않았으므로
     * 시연용 단일 카메라 CAM_SEQ = 0을 사용한다.
     *
     * 중요:
     * 기존처럼 CAMERA_ROI_INFO 전체를 삭제하지 않고,
     * CAM_SEQ = 0 데이터만 조회/삭제/교체한다.
     */
    private static final Integer DEMO_CAM_SEQ = 0;

    private final RoiInfoRepository repo;

    public RoiInfoController(RoiInfoRepository repo) {
        this.repo = repo;
    }

    // =========================================================
    // 현재 시연 카메라 ROI 전체 삭제
    // =========================================================
    @PostMapping("/roidelete")
    @ResponseBody
    public ResponseEntity<String> roidelete() {

        int deletedCount = repo.deleteAllByCamSeq(DEMO_CAM_SEQ);

        return ResponseEntity.ok(
            "SUCCESS - CAM_SEQ=" + DEMO_CAM_SEQ
            + ", deleted=" + deletedCount
        );
    }

    // =========================================================
    // 현재 시연 카메라 ROI 조회
    // =========================================================
    @GetMapping("/roiget")
    @ResponseBody
    public List<Camera_Roi_Info> roiget() {

        return repo.findAllByCamSeq(DEMO_CAM_SEQ);
    }

    // =========================================================
    // 현재 시연 카메라 ROI 저장
    // 기존 CAM_SEQ=0 ROI만 교체
    // 다른 카메라 ROI는 건드리지 않음
    // =========================================================
    @PostMapping("/roiinsert")
    @ResponseBody
    public ResponseEntity<String> roiinsert(
            @RequestBody RoiRequestDto dto) {

        try {

            if (dto.getRois() == null || dto.getRois().isEmpty()) {
                return ResponseEntity
                        .badRequest()
                        .body("저장할 ROI 데이터가 없습니다.");
            }

            // -------------------------------------------------
            // 기존 방식:
            // repo.deleteAllInBatch();
            //
            // 변경 방식:
            // 현재 시연 카메라 CAM_SEQ=0 데이터만 삭제
            // -------------------------------------------------
            repo.deleteAllByCamSeq(DEMO_CAM_SEQ);

            List<Camera_Roi_Info> entityList = new ArrayList<>();

            for (RoiRequestDto.RoiItemDto item : dto.getRois()) {

                Camera_Roi_Info entity = new Camera_Roi_Info(
                    item.getId(),
                    DEMO_CAM_SEQ,
                    item.getName(),
                    item.getX(),
                    item.getWidth(),
                    item.getY(),
                    item.getHeight()
                );

                entityList.add(entity);
            }

            repo.saveAll(entityList);

            return ResponseEntity.ok(
                "SUCCESS - CAM_SEQ=" + DEMO_CAM_SEQ
                + ", saved=" + entityList.size()
            );

        } catch (Exception e) {

            e.printStackTrace();

            return ResponseEntity
                    .status(500)
                    .body("서버 에러: " + e.getMessage());
        }
    }
}