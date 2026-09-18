"""Common frame input contracts for upload and live analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

import cv2


@dataclass(frozen=True)
class FramePacket:
    """One decoded frame and its elapsed timestamp in seconds."""

    frame: Any
    timestamp_sec: float

    def __post_init__(self) -> None:
        if self.frame is None or not hasattr(self.frame, "shape"):
            raise ValueError("frame must be a decoded image array.")
        if len(self.frame.shape) != 3 or self.frame.shape[2] != 3:
            raise ValueError("frame must be a BGR image with three channels.")
        if self.frame.shape[0] <= 0 or self.frame.shape[1] <= 0:
            raise ValueError("frame dimensions must be positive.")
        if not isinstance(self.timestamp_sec, (int, float)):
            raise ValueError("timestamp_sec must be numeric.")
        if self.timestamp_sec < 0:
            raise ValueError("timestamp_sec must be zero or greater.")


@dataclass(frozen=True)
class AnalysisContext:
    """Identifiers and metadata shared by UPLOAD and LIVE inputs."""

    analysis_id: str
    pet_id: str
    video_id: str
    camera_id: str
    species: str
    recorded_at: str
    recorded_at_source: str = "REQUEST_TIME"
    time_slot: Optional[str] = None
    roi_data: Optional[dict] = None

    def analyzer_arguments(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "pet_id": self.pet_id,
            "video_id": self.video_id,
            "camera_id": self.camera_id,
            "species": self.species,
            "recorded_at": self.recorded_at,
            "recorded_at_source": self.recorded_at_source,
            "time_slot": self.time_slot,
            "roi_data": self.roi_data,
        }


class FrameSource(ABC):
    """A source that yields timestamped decoded frames."""

    @abstractmethod
    def frames(self) -> Iterator[FramePacket]:
        raise NotImplementedError


class UploadFrameSource(FrameSource):
    """Decode an uploaded video into the common frame contract."""

    def __init__(self, video_path: str | Path) -> None:
        self.video_path = Path(video_path).expanduser().resolve()

    def frames(self) -> Iterator[FramePacket]:
        capture = cv2.VideoCapture(str(self.video_path))
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            capture.release()
            raise ValueError("Video FPS must be greater than zero.")
        frame_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                yield FramePacket(frame=frame, timestamp_sec=frame_index / fps)
                frame_index += 1
        finally:
            capture.release()


__all__ = ["FramePacket", "AnalysisContext", "FrameSource", "UploadFrameSource"]
