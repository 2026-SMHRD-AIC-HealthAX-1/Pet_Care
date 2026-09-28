package com.smhrd.myapp.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

import com.smhrd.myapp.entity.Camera_Roi_Info;
import com.smhrd.myapp.repository.RoiInfoRepository;

@Service
public class MonitoringService {

    private static final Integer DEMO_CAM_SEQ = 0;
    private static final float ROI_EDGE_EPSILON = 0.001f;

    private static final Set<String> ALLOWED_ROI_NAMES =
            Set.of("FOOD_BOWL", "WATER_BOWL", "BED", "ETC");

    private final RestClient aiClient =
            RestClient.create("http://127.0.0.1:8000");

    private final RoiInfoRepository roiInfoRepository;

    public MonitoringService(
            RoiInfoRepository roiInfoRepository) {
        this.roiInfoRepository = roiInfoRepository;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> analyzeVideo(
            MultipartFile video,
            String petId,
            String cameraId,
            String species,
            String userSeq) throws Exception {

        if (video == null || video.isEmpty()) {
            throw new IllegalArgumentException(
                    "분석할 영상 파일이 없습니다."
            );
        }

        if (userSeq == null || userSeq.isBlank()) {
            throw new IllegalArgumentException(
                    "로그인 사용자 정보가 없습니다."
            );
        }

        String normalizedSpecies =
                species == null
                        ? ""
                        : species.trim().toUpperCase(Locale.ROOT);

        if (!normalizedSpecies.equals("DOG")
                && !normalizedSpecies.equals("CAT")) {
            throw new IllegalArgumentException(
                    "species는 DOG 또는 CAT만 가능합니다."
            );
        }

        String originalFilename =
                video.getOriginalFilename() != null
                        ? video.getOriginalFilename()
                        : "uploaded_video.mp4";

        ByteArrayResource videoResource =
                new ByteArrayResource(video.getBytes()) {
                    @Override
                    public String getFilename() {
                        return originalFilename;
                    }
                };

        List<Camera_Roi_Info> savedRois =
                roiInfoRepository.findAllByCamSeq(DEMO_CAM_SEQ);

        String roiJson = null;

        if (savedRois != null && !savedRois.isEmpty()) {
            List<SafeRoi> safeRois =
                    normalizeSavedRois(savedRois);

            if (!safeRois.isEmpty()) {
                roiJson =
                        buildRoiJson(
                                cameraId,
                                safeRois
                        );

                System.out.println(
                        "[UPLOAD ROI 연결] cameraId="
                                + cameraId
                                + ", dbRoiCount="
                                + savedRois.size()
                                + ", safeRoiCount="
                                + safeRois.size()
                                + ", roiData="
                                + roiJson
                );

            } else {
                System.err.println(
                        "[UPLOAD ROI 경고] DB ROI가 모두 유효하지 않아 "
                                + "ROI 없이 분석을 진행합니다."
                );
            }

        } else {
            System.out.println(
                    "[UPLOAD ROI 연결] CAM_SEQ="
                            + DEMO_CAM_SEQ
                            + " 저장 ROI 없음"
            );
        }

        MultipartBodyBuilder builder =
                new MultipartBodyBuilder();

        builder.part("video", videoResource)
                .filename(originalFilename)
                .contentType(
                        video.getContentType() != null
                                ? MediaType.parseMediaType(
                                        video.getContentType()
                                )
                                : MediaType.APPLICATION_OCTET_STREAM
                );

        builder.part("pet_id", petId);
        builder.part("camera_id", cameraId);
        builder.part("species", normalizedSpecies);
        builder.part("user_seq", userSeq);

        if (roiJson != null) {
            builder.part("roi_data", roiJson);
        }

        MultiValueMap<String, ?> multipartBody =
                builder.build();

        return aiClient.post()
                .uri("/analyze-upload")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(multipartBody)
                .retrieve()
                .body(Map.class);
    }

    private List<SafeRoi> normalizeSavedRois(
            List<Camera_Roi_Info> rois) {

        List<SafeRoi> safe =
                new ArrayList<>();

        for (Camera_Roi_Info roi : rois) {
            try {
                safe.add(normalizeRoi(roi));

            } catch (IllegalArgumentException e) {
                System.err.println(
                        "[UPLOAD ROI 제외] seq="
                                + roi.getSeq()
                                + ", reason="
                                + e.getMessage()
                );
            }
        }

        return safe;
    }

    private SafeRoi normalizeRoi(
            Camera_Roi_Info roi) {

        if (roi == null
                || roi.getSeq() == null
                || roi.getSeq().isBlank()) {
            throw new IllegalArgumentException(
                    "ROI id가 없습니다."
            );
        }

        String rawName = roi.getRoi_name();

        if (rawName == null || rawName.isBlank()) {
            throw new IllegalArgumentException(
                    "ROI name이 없습니다."
            );
        }

        String name =
                rawName.trim().toUpperCase(Locale.ROOT);

        if (!ALLOWED_ROI_NAMES.contains(name)) {
            throw new IllegalArgumentException(
                    "허용되지 않은 ROI name: " + name
            );
        }

        Float rawX = roi.getX_start();
        Float rawY = roi.getY_start();
        Float rawWidth = roi.getWidth();
        Float rawHeight = roi.getHeight();

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
                    "width/height가 0 이하입니다."
            );
        }

        if (x < -ROI_EDGE_EPSILON
                || y < -ROI_EDGE_EPSILON
                || x > 1f + ROI_EDGE_EPSILON
                || y > 1f + ROI_EDGE_EPSILON) {
            throw new IllegalArgumentException(
                    "x/y가 화면 범위를 벗어났습니다."
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
                    "보정 후 ROI 크기가 0입니다."
            );
        }

        return new SafeRoi(
                roi.getSeq().trim(),
                name,
                round6(safeLeft),
                round6(safeTop),
                round6(safeWidth),
                round6(safeHeight)
        );
    }

    private String buildRoiJson(
            String cameraId,
            List<SafeRoi> rois) {

        StringBuilder json =
                new StringBuilder();

        json.append("{");
        json.append("\"camera_id\":\"")
                .append(escapeJson(cameraId))
                .append("\",");
        json.append("\"roi_areas\":[");

        for (int i = 0; i < rois.size(); i++) {
            SafeRoi roi = rois.get(i);

            if (i > 0) {
                json.append(",");
            }

            json.append("{");
            json.append("\"roi_id\":\"")
                    .append(escapeJson(roi.id()))
                    .append("\",");
            json.append("\"roi_name\":\"")
                    .append(escapeJson(roi.name()))
                    .append("\",");
            json.append("\"roi_type\":\"RECTANGLE\",");
            json.append("\"x\":")
                    .append(roi.x())
                    .append(",");
            json.append("\"y\":")
                    .append(roi.y())
                    .append(",");
            json.append("\"width\":")
                    .append(roi.width())
                    .append(",");
            json.append("\"height\":")
                    .append(roi.height());
            json.append("}");
        }

        json.append("]");
        json.append("}");

        return json.toString();
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

    private String escapeJson(String value) {
        if (value == null) {
            return "";
        }

        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"");
    }

    private record SafeRoi(
            String id,
            String name,
            float x,
            float y,
            float width,
            float height) {
    }
}
