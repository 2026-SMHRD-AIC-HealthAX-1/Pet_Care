package com.smhrd.myapp.dto;

import java.util.List;

public class RoiRequestDto {

    private String camera_id;
    private String video;
    private List<RoiItemDto> rois;

    public RoiRequestDto() {}

    // Getter & Setter
    public String getCamera_id() {
        return camera_id;
    }

    public void setCamera_id(String camera_id) {
        this.camera_id = camera_id;
    }

    public String getVideo() {
        return video;
    }

    public void setVideo(String video) {
        this.video = video;
    }

    public List<RoiItemDto> getRois() {
        return rois;
    }

    public void setRois(List<RoiItemDto> rois) {
        this.rois = rois;
    }

    // 내부 클래스
    public static class RoiItemDto {
    	private Integer seq;
        private String id;
        private String name;
        private Float x;
        private Float y;
        private Float width;
        private Float height;

        public RoiItemDto() {}

        // Getter & Setter
        public Integer getSeq() {
            return seq;
        }

        public void setSeq(Integer seq) {
            this.seq = seq;
        }
        
        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public Float getX() {
            return x;
        }

        public void setX(Float x) {
            this.x = x;
        }

        public Float getY() {
            return y;
        }

        public void setY(Float y) {
            this.y = y;
        }

        public Float getWidth() {
            return width;
        }

        public void setWidth(Float width) {
            this.width = width;
        }

        public Float getHeight() {
            return height;
        }

        public void setHeight(Float height) {
            this.height = height;
        }
    }
}
