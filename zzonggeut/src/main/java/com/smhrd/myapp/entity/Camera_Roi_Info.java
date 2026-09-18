package com.smhrd.myapp.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "CAMERA_ROI_INFO")
@Getter
@NoArgsConstructor
public class Camera_Roi_Info 
{
	@Id
    // @GeneratedValue 어노테이션을 완전히 삭제/주석 처리해야 개발자가 직접 넣는 seq 값을 사용합니다.
    @Column(name = "SEQ", nullable = false)
    private String seq;

    @Column(name = "CAM_SEQ")
    private Integer cam_seq;
    
    @Column(name = "ROI_NAME")
    private String roi_name;

    @Column(name = "X_START")
    private Float x_start;

    @Column(name = "WIDTH")
    private Float width;

    @Column(name = "Y_START")
    private Float y_start;

    @Column(name = "HEIGHT")
    private Float height;

    // seq를 포함해 모든 값을 세팅하는 생성자
    public Camera_Roi_Info(String seq, Integer cam_seq, String roi_name, Float x_start, Float width, Float y_start, Float height) {
        this.seq = seq;
        this.cam_seq = cam_seq;
        this.roi_name = roi_name;
        this.x_start = x_start;
        this.width = width;
        this.y_start = y_start;
        this.height = height;
    }

    // Getter & Setter 직접 작성
    //public Integer getSeq() { return seq; }
    public void setSeq(String seq) { this.seq = seq; }
    //public Integer getCam_seq() { return cam_seq; }
    public void setCam_seq(Integer cam_seq) { this.cam_seq = cam_seq; }
    //public String getRoi_name() { return roi_name; }
    public void setRoi_name(String roi_name) { this.roi_name = roi_name; }
    //public Float getX_start() { return x_start; }
    public void setX_start(Float x_start) { this.x_start = x_start; }
    //public Float getWidth() { return width; }
    public void setWidth(Float width) { this.width = width; }
    //public Float getY_start() { return y_start; }
    public void setY_start(Float y_start) { this.y_start = y_start; }
    //public Float getHeight() { return height; }
    public void setHeight(Float height) { this.height = height; }
}
