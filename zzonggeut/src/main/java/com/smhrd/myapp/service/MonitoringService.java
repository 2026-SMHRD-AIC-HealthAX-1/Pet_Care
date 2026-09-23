package com.smhrd.myapp.service;

import java.util.List;
import java.util.Map;

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

    private final RestClient aiClient =
            RestClient.create("http://127.0.0.1:8000");

    private final RoiInfoRepository roiInfoRepository;

    public MonitoringService(
            RoiInfoRepository roiInfoRepository) {

        this.roiInfoRepository =
                roiInfoRepository;
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
                        : species.trim().toUpperCase();

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

        // ==========================================
        // DB ROI 조회
        // ==========================================

        List<Camera_Roi_Info> savedRois =
                roiInfoRepository.findAllByCamSeq(
                        DEMO_CAM_SEQ
                );

        String roiJson = null;

        if (savedRois != null
                && !savedRois.isEmpty()) {

            roiJson =
                    buildRoiJson(
                            cameraId,
                            savedRois
                    );

            System.out.println(
                    "[UPLOAD ROI 연결] "
                    + "cameraId=" + cameraId
                    + ", roiCount=" + savedRois.size()
                    + ", roiData=" + roiJson
            );

        } else {

            System.out.println(
                    "[UPLOAD ROI 연결] "
                    + "CAM_SEQ="
                    + DEMO_CAM_SEQ
                    + " 저장 ROI 없음"
            );
        }

        // ==========================================
        // Multipart 요청 구성
        // ==========================================

        MultipartBodyBuilder builder =
                new MultipartBodyBuilder();

        builder.part(
                        "video",
                        videoResource
                )
                .filename(
                        originalFilename
                )
                .contentType(
                        video.getContentType() != null
                                ? MediaType.parseMediaType(
                                        video.getContentType()
                                )
                                : MediaType.APPLICATION_OCTET_STREAM
                );

        builder.part(
                "pet_id",
                petId
        );

        builder.part(
                "camera_id",
                cameraId
        );

        builder.part(
                "species",
                normalizedSpecies
        );

        builder.part(
                "user_seq",
                userSeq
        );

        if (roiJson != null) {

            builder.part(
                    "roi_data",
                    roiJson
            );
        }

        MultiValueMap<String, ?> multipartBody =
                builder.build();

        // ==========================================
        // AI 서버 요청
        // ==========================================

        return aiClient.post()
                .uri("/analyze-upload")
                .contentType(
                        MediaType.MULTIPART_FORM_DATA
                )
                .body(
                        multipartBody
                )
                .retrieve()
                .body(
                        Map.class
                );
    }

    // ==========================================
    // ROI JSON 생성
    // ==========================================

    private String buildRoiJson(
            String cameraId,
            List<Camera_Roi_Info> rois) {

        StringBuilder json =
                new StringBuilder();

        json.append("{");

        json.append("\"camera_id\":\"")
                .append(
                        escapeJson(
                                cameraId
                        )
                )
                .append("\",");

        json.append(
                "\"roi_areas\":["
        );

        for (
                int i = 0;
                i < rois.size();
                i++
        ) {

            Camera_Roi_Info roi =
                    rois.get(i);

            if (i > 0) {
                json.append(",");
            }

            json.append("{");

            json.append("\"roi_id\":\"")
                    .append(
                            escapeJson(
                                    String.valueOf(
                                            roi.getSeq()
                                    )
                            )
                    )
                    .append("\",");

            json.append("\"roi_name\":\"")
                    .append(
                            escapeJson(
                                    roi.getRoi_name()
                            )
                    )
                    .append("\",");

            json.append(
                    "\"roi_type\":\"RECTANGLE\","
            );

            json.append("\"x\":")
                    .append(
                            roi.getX_start()
                    )
                    .append(",");

            json.append("\"y\":")
                    .append(
                            roi.getY_start()
                    )
                    .append(",");

            json.append("\"width\":")
                    .append(
                            roi.getWidth()
                    )
                    .append(",");

            json.append("\"height\":")
                    .append(
                            roi.getHeight()
                    );

            json.append("}");
        }

        json.append("]");

        json.append("}");

        return json.toString();
    }

    private String escapeJson(
            String value) {

        if (value == null) {
            return "";
        }

        return value
                .replace(
                        "\\",
                        "\\\\"
                )
                .replace(
                        "\"",
                        "\\\""
                );
    }
}