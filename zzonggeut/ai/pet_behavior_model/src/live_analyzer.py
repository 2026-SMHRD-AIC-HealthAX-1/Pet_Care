"""Incremental LIVE analysis with session-scoped YOLO/ByteTrack state."""
from __future__ import annotations

import csv, json, math, tempfile, threading, time
from pathlib import Path
from typing import Any, Optional, Protocol
import cv2

from .frame_sources import AnalysisContext, FramePacket
from .live_processing import (MAX_GAP_SECONDS, PET_CLASS_IDS, PET_CLASS_NAMES,
    YOLO_CONFIDENCE, YOLO_IMAGE_SIZE, YOLO_IOU, calculate_features,
    calculate_movements, interval_features, postprocess_tracking, tracking_quality)
from .pet_behavior_analyzer import AnalyzerInputError, PetBehaviorAnalyzer
from .roi_models import parse_roi_request
from .roi_space_analyzer import analyze_roi_usage

class LiveSessionError(RuntimeError): pass
class LiveSessionClosedError(LiveSessionError): pass
class LiveFrameTimestampError(LiveSessionError, ValueError): pass
class LiveFrameShapeError(LiveSessionError, ValueError): pass
class EmptyLiveSessionError(LiveSessionError, ValueError): pass

class LiveDetector(Protocol):
    def track(self, frame: Any) -> list[dict[str, Any]]: ...

class YoloLiveDetector:
    """Load YOLO once and preserve ByteTrack state for one session."""
    def __init__(self, species: str, model_path: str = "yolo11s.pt"):
        from ultralytics import YOLO
        self.class_id = PET_CLASS_IDS[species.lower()]
        self.model = YOLO(model_path)
    def track(self, frame):
        results = self.model.track(source=frame, persist=True, classes=[self.class_id],
            tracker="bytetrack.yaml", imgsz=YOLO_IMAGE_SIZE, conf=YOLO_CONFIDENCE,
            iou=YOLO_IOU, verbose=False)
        result = results[0] if results else None
        if result is None or result.boxes is None or len(result.boxes) == 0: return []
        boxes = result.boxes.xyxy.cpu().numpy(); confs = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.int().cpu().tolist()
        ids = result.boxes.id.int().cpu().tolist() if result.boxes.id is not None else [None]*len(boxes)
        return [{"center_x":float((b[0]+b[2])/2), "center_y":float((b[1]+b[3])/2),
                 "confidence":float(c), "track_id":tid, "class_id":cid}
                for b,c,tid,cid in zip(boxes,confs,ids,classes) if cid == self.class_id]

class LiveAnalysisSession:
    def __init__(self, context, analyzer, expected_fps, temp_root=None, max_gap_sec=30.0,
                 detector=None, retain_video=True):
        if expected_fps <= 0 or expected_fps > 240: raise AnalyzerInputError("expected_fps must be greater than 0 and at most 240.")
        if max_gap_sec <= 0: raise AnalyzerInputError("max_gap_sec must be greater than zero.")
        if context.species.upper() not in {"DOG","CAT"}: raise AnalyzerInputError("species must be CAT or DOG.")
        self.context=context; self.analyzer=analyzer; self.expected_fps=float(expected_fps)
        self.max_gap_sec=float(max_gap_sec); self.detector=detector or YoloLiveDetector(context.species)
        self.retain_video=retain_video; self._temp_dir=tempfile.TemporaryDirectory(prefix="pet_live_",dir=temp_root)
        self._video_path=Path(self._temp_dir.name)/f"{context.analysis_id}_live.avi"
        self._writer=None; self._frame_size=None; self._first_timestamp=None; self._last_timestamp=None
        self._last_timeline_index=-1; self._records=[]; self._completed_intervals=[]; self._polled_count=0
        self._processing_times=[]; self._closed=False; self._lock=threading.Lock()
        self._roi_request=parse_roi_request(context.roi_data, expected_camera_id=context.camera_id)
    @property
    def received_frame_count(self): return len(self._records)
    def push_frame(self, frame, timestamp_sec):
        packet=FramePacket(frame=frame,timestamp_sec=timestamp_sec)
        with self._lock:
            self._ensure_open()
            if self._last_timestamp is not None and packet.timestamp_sec <= self._last_timestamp: raise LiveFrameTimestampError("LIVE timestamps must be strictly increasing.")
            if self._last_timestamp is not None and packet.timestamp_sec-self._last_timestamp > self.max_gap_sec: raise LiveFrameTimestampError(f"LIVE frame gap exceeds max_gap_sec ({self.max_gap_sec}).")
            h,w=packet.frame.shape[:2]
            if self._frame_size is None:
                self._frame_size=(w,h); self._first_timestamp=float(packet.timestamp_sec)
                if self.retain_video: self._start_writer(w,h)
            elif self._frame_size != (w,h): raise LiveFrameShapeError(f"Frame size changed from {self._frame_size} to {(w,h)}.")
            index=round((float(packet.timestamp_sec)-self._first_timestamp)*self.expected_fps)
            if index <= self._last_timeline_index: raise LiveFrameTimestampError("Timestamp interval is shorter than the configured expected_fps slot.")
            if self._writer is not None:
                import numpy as np
                black=np.zeros((h,w,3),dtype=np.uint8)
                for _ in range(self._last_timeline_index+1,index): self._writer.write(black)
                self._writer.write(packet.frame)
            started=time.perf_counter(); detections=self.detector.track(packet.frame)
            self._processing_times.append(time.perf_counter()-started)
            selected=self._select(detections); self._records.append(self._record(selected,float(packet.timestamp_sec)))
            self._last_timeline_index=index; self._last_timestamp=float(packet.timestamp_sec)
            new=self._refresh_intervals(); return new[-1] if new else None
    def poll_intervals(self):
        with self._lock:
            result=self._completed_intervals[self._polled_count:]; self._polled_count=len(self._completed_intervals)
            return [dict(item) for item in result]
    def finish(self):
        with self._lock:
            self._ensure_open()
            if not self._records: self._close(); raise EmptyLiveSessionError("At least one LIVE frame is required.")
            self._release_writer(); self._closed=True; artifacts=self._write_artifacts(self._processed())
        try:
            if not isinstance(self.analyzer, PetBehaviorAnalyzer):
                return self.analyzer.analyze(video_path=self._video_path,**self.context.analyzer_arguments())
            return self.analyzer.analyze_precomputed(video_path=self._video_path,
                precomputed_artifacts=artifacts,**self.context.analyzer_arguments())
        finally: self._temp_dir.cleanup()
    def abort(self):
        with self._lock:
            if not self._closed: self._close()
    def metrics(self):
        total=sum(self._processing_times)
        return {"processed_frames":len(self._processing_times),"processing_fps":len(self._processing_times)/total if total else None,
                "average_frame_latency_sec":total/len(self._processing_times) if self._processing_times else None,
                "max_frame_latency_sec":max(self._processing_times) if self._processing_times else None}
    def _select(self,detections):
        cid=PET_CLASS_IDS[self.context.species.lower()]; candidates=[d for d in detections if int(d.get("class_id",-1))==cid]
        if not candidates:return None
        previous=next((r for r in reversed(self._records) if r["raw_x"] is not None),None)
        if previous is None:return max(candidates,key=lambda d:d.get("confidence",0))
        return min(candidates,key=lambda d:math.hypot(d["center_x"]-previous["raw_x"],d["center_y"]-previous["raw_y"]))
    def _record(self,d,timestamp):
        species=self.context.species.lower(); cid=PET_CLASS_IDS[species]
        return {"frame":len(self._records)+1,"time_sec":timestamp,"pet_id":1,"pet_type":species,"class_id":cid,
            "predicted_type":PET_CLASS_NAMES.get(d.get("class_id")) if d else None,"predicted_class_id":d.get("class_id") if d else None,
            "raw_track_id":d.get("track_id") if d else None,"confidence":d.get("confidence") if d else None,
            "raw_x":d.get("center_x") if d else None,"raw_y":d.get("center_y") if d else None,"center_x":None,"center_y":None,
            "source_detected":d is not None,"status":"detected" if d else "missing"}
    def _processed(self): return postprocess_tracking(self._records,self.expected_fps,math.hypot(*self._frame_size))
    def _refresh_intervals(self):
        stable_end=self._last_timestamp-MAX_GAP_SECONDS; rows=self._processed()
        raw=interval_features(rows,math.hypot(*self._frame_size),True,stable_end); existing=len(self._completed_intervals)
        roi=analyze_roi_usage(rows,self._roi_request,*self._frame_size) if self._roi_request else None
        # analyze_roi_usage finalizes an open visit as VIDEO_END.  During a LIVE
        # session it is not an end yet, so intermediate payloads expose only
        # completed EXIT events; finish() retains the final VIDEO_END contract.
        if roi is not None:
            for result in roi["roi_results"]:
                events=[event for event in result["visit_events"] if event["end_reason"]=="EXIT"]
                result["visit_events"]=events; result["approach_count"]=len(events)
                result["approach_times_sec"]=[event["entry_time_sec"] for event in events]
                result["first_approach_time_sec"]=result["approach_times_sec"][0] if events else None
                result["stay_time_sec"]=round(sum(event["stay_time_sec"] for event in events),6)
        quality=tracking_quality(rows,self.context.species)
        for item in raw[existing:]:
            self._completed_intervals.append({"analysis_id":self.context.analysis_id,"pet_id":self.context.pet_id,"camera_id":self.context.camera_id,
              "species":self.context.species.upper(),"start_sec":item["interval_start_sec"],"end_sec":item["interval_end_sec"],
              "activity_level":item["activity_level"],"stationary_ratio":item["stationary_ratio"],
              "normalized_travel_distance":item["travel_distance"],"normalized_moving_speed":item["moving_speed"],
              "tracking_quality":{"quality_status":quality["tracking_quality"],"detection_rate":quality["detection_rate"],"missing_ratio":quality["missing_ratio"]},
              "space_analysis":roi})
        return self._completed_intervals[existing:]
    def _write_artifacts(self,rows):
        diagonal=math.hypot(*self._frame_size); intervals=interval_features(rows,diagonal,False,self._last_timestamp)
        overall=calculate_features(calculate_movements(rows,diagonal)); quality=tracking_quality(rows,self.context.species)
        roi=analyze_roi_usage(rows,self._roi_request,*self._frame_size) if self._roi_request else None
        directory=Path(self._temp_dir.name)/"artifacts"; directory.mkdir(); paths={k:directory/f"{k}.csv" for k in ("tracking","quality","features","interval_features")}
        fields=["frame","time_sec","pet_id","pet_type","class_id","predicted_type","predicted_class_id","raw_track_id","confidence","raw_x","raw_y","center_x","center_y","source_detected","status"]
        self._csv(paths["tracking"],fields,rows); self._csv(paths["quality"],["video",*quality.keys()],[{"video":self._video_path.name,**quality}])
        self._csv(paths["features"],["activity_level","stationary_ratio","travel_distance","moving_speed"],[overall])
        self._csv(paths["interval_features"],["interval_start_sec","interval_end_sec","activity_level","stationary_ratio","travel_distance","moving_speed","moving_count","stationary_count","measurement_count","analyzed_duration"],intervals)
        if roi is not None:
            paths["space_analysis"]=directory/"space_analysis.json"; paths["space_analysis"].write_text(json.dumps(roi,ensure_ascii=False,indent=2),encoding="utf-8")
        else: paths["space_analysis"]=None
        return paths
    @staticmethod
    def _csv(path,fields,rows):
        with path.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
    def _start_writer(self,w,h):
        self._writer=cv2.VideoWriter(str(self._video_path),cv2.VideoWriter_fourcc(*"MJPG"),self.expected_fps,(w,h))
        if not self._writer.isOpened(): self._writer.release(); self._close(); raise LiveSessionError("Cannot create temporary LIVE video.")
    def _release_writer(self):
        if self._writer is not None:self._writer.release(); self._writer=None
    def _close(self): self._release_writer(); self._closed=True; self._temp_dir.cleanup()
    def _ensure_open(self):
        if self._closed: raise LiveSessionClosedError("LIVE session is already closed.")

class LivePetBehaviorAnalyzer:
    def __init__(self,analyzer:Optional[PetBehaviorAnalyzer]=None,temp_root=None,detector_factory=None):
        self.analyzer=analyzer or PetBehaviorAnalyzer(); self.temp_root=temp_root; self.detector_factory=detector_factory
    def start_session(self,*,context,expected_fps,max_gap_sec=30.0):
        detector=self.detector_factory(context.species) if self.detector_factory else None
        return LiveAnalysisSession(context,self.analyzer,expected_fps,self.temp_root,max_gap_sec,detector)

__all__=["LivePetBehaviorAnalyzer","LiveAnalysisSession","LiveDetector","YoloLiveDetector","LiveSessionError","LiveSessionClosedError","LiveFrameTimestampError","LiveFrameShapeError","EmptyLiveSessionError"]
