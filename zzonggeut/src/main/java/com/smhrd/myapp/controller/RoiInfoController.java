package com.smhrd.myapp.controller;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseBody;

import com.smhrd.myapp.dto.RoiRequestDto;
import com.smhrd.myapp.entity.Camera_Roi_Info;
import com.smhrd.myapp.repository.RoiInfoRepository;

@Controller
public class RoiInfoController {

    private static final Integer DEMO_CAM_SEQ = 0;
    private static final float ROI_EDGE_EPSILON = 0.001f;

    private static final Set<String> ALLOWED_ROI_NAMES =
            Set.of("FOOD_BOWL", "WATER_BOWL", "BED", "ETC");

    private final RoiInfoRepository repo;

    public RoiInfoController(RoiInfoRepository repo) {
        this.repo = repo;
    }

    @PostMapping("/roidelete")
    @ResponseBody
    public ResponseEntity<String> roidelete() {
        int deletedCount = repo.deleteAllByCamSeq(DEMO_CAM_SEQ);
        return ResponseEntity.ok(
                "SUCCESS - CAM_SEQ=" + DEMO_CAM_SEQ
                        + ", deleted=" + deletedCount
        );
    }

    @GetMapping("/roiget")
    @ResponseBody
    public List<Map<String, Object>> roiget() {
        List<Camera_Roi_Info> saved =
                repo.findAllByCamSeq(DEMO_CAM_SEQ);

        List<Map<String, Object>> safe =
                new ArrayList<>();

        for (Camera_Roi_Info roi : saved) {
            try {
                NormalizedRoi normalized =
                        normalizeRoi(
                                roi.getSeq(),
                                roi.getRoi_name(),
                                roi.getX_start(),
                                roi.getY_start(),
                                roi.getWidth(),
                                roi.getHeight()
                        );

                Map<String, Object> row =
                        new LinkedHashMap<>();

                row.put("seq", normalized.id());
                row.put("cam_seq", DEMO_CAM_SEQ);
                row.put("roi_name", normalized.name());
                row.put("x_start", normalized.x());
                row.put("width", normalized.width());
                row.put("y_start", normalized.y());
                row.put("height", normalized.height());

                safe.add(row);

            } catch (IllegalArgumentException e) {
                System.err.println(
                        "[ROI 조회 제외] seq="
                                + roi.getSeq()
                                + ", reason="
                                + e.getMessage()
                );
            }
        }

        return safe;
    }

    @PostMapping("/roiinsert")
    @ResponseBody
    @Transactional
    public ResponseEntity<String> roiinsert(
            @RequestBody RoiRequestDto dto) {

        if (dto == null
                || dto.getRois() == null
                || dto.getRois().isEmpty()) {
            return ResponseEntity
                    .badRequest()
                    .body("저장할 ROI 데이터가 없습니다.");
        }

        List<Camera_Roi_Info> entityList =
                new ArrayList<>();

        try {
            for (RoiRequestDto.RoiItemDto item : dto.getRois()) {
                NormalizedRoi roi =
                        normalizeRoi(
                                item.getId(),
                                item.getName(),
                                item.getX(),
                                item.getY(),
                                item.getWidth(),
                                item.getHeight()
                        );

                entityList.add(
                        new Camera_Roi_Info(
                                roi.id(),
                                DEMO_CAM_SEQ,
                                roi.name(),
                                roi.x(),
                                roi.width(),
                                roi.y(),
                                roi.height()
                        )
                );
            }

        } catch (IllegalArgumentException e) {
            return ResponseEntity
                    .badRequest()
                    .body("ROI 좌표 오류: " + e.getMessage());
        }

        repo.deleteAllByCamSeq(DEMO_CAM_SEQ);
        repo.saveAll(entityList);

        return ResponseEntity.ok(
                "SUCCESS - CAM_SEQ=" + DEMO_CAM_SEQ
                        + ", saved=" + entityList.size()
        );
    }

    private NormalizedRoi normalizeRoi(
            String id,
            String rawName,
            Float rawX,
            Float rawY,
            Float rawWidth,
            Float rawHeight) {

        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException(
                    "ROI id가 비어 있습니다."
            );
        }

        if (rawName == null || rawName.isBlank()) {
            throw new IllegalArgumentException(
                    "ROI name이 비어 있습니다."
            );
        }

        String name =
                rawName.trim().toUpperCase(Locale.ROOT);

        if (!ALLOWED_ROI_NAMES.contains(name)) {
            throw new IllegalArgumentException(
                    "허용되지 않은 ROI name: " + name
            );
        }

        validateFinite("x", rawX);
        validateFinite("y", rawY);
        validateFinite("width", rawWidth);
        validateFinite("height", rawHeight);

        float x = rawX;
        float y = rawY;
        float width = rawWidth;
        float height = rawHeight;

        if (width <= 0f || height <= 0f) {
            throw new IllegalArgumentException(
                    "width와 height는 0보다 커야 합니다."
            );
        }

        if (x < -ROI_EDGE_EPSILON
                || y < -ROI_EDGE_EPSILON
                || x > 1f + ROI_EDGE_EPSILON
                || y > 1f + ROI_EDGE_EPSILON) {
            throw new IllegalArgumentException(
                    "x/y가 허용 범위를 벗어났습니다."
            );
        }

        float right = x + width;
        float bottom = y + height;

        if (right < -ROI_EDGE_EPSILON
                || bottom < -ROI_EDGE_EPSILON
                || right > 1f + ROI_EDGE_EPSILON
                || bottom > 1f + ROI_EDGE_EPSILON) {
            throw new IllegalArgumentException(
                    "ROI 영역이 화면 범위를 벗어났습니다."
            );
        }

        float safeLeft = clamp01(x);
        float safeTop = clamp01(y);
        float safeRight = clamp01(right);
        float safeBottom = clamp01(bottom);

        float safeWidth = safeRight - safeLeft;
        float safeHeight = safeBottom - safeTop;

        if (safeWidth <= 0f || safeHeight <= 0f) {
            throw new IllegalArgumentException(
                    "보정 후 ROI 크기가 0이 되었습니다."
            );
        }

        return new NormalizedRoi(
                id.trim(),
                name,
                round6(safeLeft),
                round6(safeTop),
                round6(safeWidth),
                round6(safeHeight)
        );
    }

    private void validateFinite(
            String field,
            Float value) {
        if (value == null || !Float.isFinite(value)) {
            throw new IllegalArgumentException(
                    field + " 값이 유효한 숫자가 아닙니다."
            );
        }
    }

    private float clamp01(float value) {
        return Math.max(0f, Math.min(1f, value));
    }

    private float round6(float value) {
        return Math.round(value * 1_000_000f)
                / 1_000_000f;
    }

    private record NormalizedRoi(
            String id,
            String name,
            float x,
            float y,
            float width,
            float height) {
    }
}
