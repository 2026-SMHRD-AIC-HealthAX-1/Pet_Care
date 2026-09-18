"""Local-only real YOLO LIVE regression and latency measurement."""
from __future__ import annotations
import argparse, json, time, uuid
from pathlib import Path
import cv2
from src import AnalysisContext, LivePetBehaviorAnalyzer, PetBehaviorAnalyzer

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("video",type=Path); parser.add_argument("species",choices=["DOG","CAT"])
    parser.add_argument("--camera-id",default="CAM-LOCAL-LIVE")
    args=parser.parse_args(); capture=cv2.VideoCapture(str(args.video.resolve()))
    if not capture.isOpened(): raise SystemExit(f"Cannot open: {args.video}")
    fps=capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0: raise SystemExit("Video FPS must be positive")
    token=uuid.uuid4().hex[:10]
    context=AnalysisContext(analysis_id=f"ANL-LIVE-{token}",pet_id=f"PET-{args.species}-{token}",
        video_id=f"VID-LIVE-{token}",camera_id=args.camera_id,species=args.species,
        recorded_at=time.strftime("%Y-%m-%dT%H:%M:%S+09:00"))
    session=LivePetBehaviorAnalyzer().start_session(context=context,expected_fps=fps)
    started=time.perf_counter(); index=0; interval_arrivals=[]
    while True:
        ok,frame=capture.read()
        if not ok: break
        emitted=session.push_frame(frame,index/fps)
        if emitted is not None: interval_arrivals.append({"end_sec":emitted["end_sec"],"wall_sec":time.perf_counter()-started})
        index += 1
    capture.release(); metrics=session.metrics(); result=session.finish()
    upload=PetBehaviorAnalyzer().analyze(video_path=args.video,analysis_id=f"ANL-UPLOAD-{token}",
        pet_id=context.pet_id,video_id=f"VID-UPLOAD-{token}",camera_id=args.camera_id,species=args.species,
        recorded_at=context.recorded_at)
    print(json.dumps({"live_status":result["analysis_status"],"live_schema":result["schema_version"],
        "upload_status":upload["analysis_status"],"upload_schema":upload["schema_version"],
        "metrics":metrics,"interval_arrivals":interval_arrivals,"input_fps":fps,
        "backlog_risk":metrics["processing_fps"] is not None and metrics["processing_fps"] < fps},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
