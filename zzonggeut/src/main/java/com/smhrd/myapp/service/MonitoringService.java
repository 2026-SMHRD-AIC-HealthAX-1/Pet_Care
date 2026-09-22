package com.smhrd.myapp.service;

import java.util.Map;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

@Service
public class MonitoringService {

    private final RestClient aiClient =
            RestClient.create("http://127.0.0.1:8000");

    @SuppressWarnings("unchecked")
    public Map<String, Object> analyzeVideo(
            MultipartFile video,
            String petId,
            String cameraId,
            String species) throws Exception {

        if (video == null || video.isEmpty()) {
            throw new IllegalArgumentException(
                    "분석할 영상 파일이 없습니다."
            );
        }

        String normalizedSpecies = species == null
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

        MultiValueMap<String, ?> multipartBody =
                builder.build();

        return aiClient.post()
                .uri(uriBuilder -> uriBuilder
                        .path("/analyze-upload")
                        .queryParam("pet_id", petId)
                        .queryParam("camera_id", cameraId)
                        .queryParam(
                                "species",
                                normalizedSpecies
                        )
                        .build())
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(multipartBody)
                .retrieve()
                .body(Map.class);
    }
}