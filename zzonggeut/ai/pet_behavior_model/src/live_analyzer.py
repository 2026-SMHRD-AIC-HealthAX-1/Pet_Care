"""LIVE frame session adapter for the existing video pipeline."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .frame_sources import AnalysisContext, FramePacket
from .pet_behavior_analyzer import AnalyzerInputError, PetBehaviorAnalyzer


class LiveSessionError(RuntimeError):
    """Base error for invalid LIVE session state or frame input."""


class LiveSessionClosedError(LiveSessionError):
    """The caller tried to use a completed or aborted session."""


class LiveFrameTimestampError(LiveSessionError, ValueError):
    """Frame timestamps are not strictly increasing."""


class LiveFrameShapeError(LiveSessionError, ValueError):
    """A frame does not match the first frame's dimensions."""


class EmptyLiveSessionError(LiveSessionError, ValueError):
    """No valid frame was supplied before finish()."""


class LiveAnalysisSession:
    """Receive LIVE frames, then reuse the validated upload video pipeline.

    Missing timestamp slots are encoded as black frames. This makes the
    existing tracker observe a real detection gap instead of silently joining
    positions across a camera interruption.
    """

    def __init__(
        self,
        context: AnalysisContext,
        analyzer: PetBehaviorAnalyzer,
        expected_fps: float,
        temp_root: str | Path | None = None,
        max_gap_sec: float = 30.0,
    ) -> None:
        if expected_fps <= 0 or expected_fps > 240:
            raise AnalyzerInputError("expected_fps must be greater than 0 and at most 240.")
        if max_gap_sec <= 0:
            raise AnalyzerInputError("max_gap_sec must be greater than zero.")
        self.context = context
        self.analyzer = analyzer
        self.expected_fps = float(expected_fps)
        self.max_gap_sec = float(max_gap_sec)
        self._temp_dir = tempfile.TemporaryDirectory(prefix="pet_live_", dir=temp_root)
        self._video_path = Path(self._temp_dir.name) / f"{context.analysis_id}_live.avi"
        self._writer: Optional[cv2.VideoWriter] = None
        self._frame_size: Optional[tuple[int, int]] = None
        self._first_timestamp: Optional[float] = None
        self._last_timestamp: Optional[float] = None
        self._last_timeline_index = -1
        self._received_frames = 0
        self._closed = False
        self._lock = threading.Lock()

    @property
    def received_frame_count(self) -> int:
        return self._received_frames

    def push_frame(self, frame, timestamp_sec: float) -> None:
        """Append one BGR frame with a monotonic elapsed timestamp."""
        packet = FramePacket(frame=frame, timestamp_sec=timestamp_sec)
        with self._lock:
            self._ensure_open()
            if self._last_timestamp is not None and packet.timestamp_sec <= self._last_timestamp:
                raise LiveFrameTimestampError("LIVE timestamps must be strictly increasing.")
            if (
                self._last_timestamp is not None
                and packet.timestamp_sec - self._last_timestamp > self.max_gap_sec
            ):
                raise LiveFrameTimestampError(
                    f"LIVE frame gap exceeds max_gap_sec ({self.max_gap_sec})."
                )

            height, width = packet.frame.shape[:2]
            if self._writer is None:
                self._start_writer(width, height)
                self._first_timestamp = float(packet.timestamp_sec)
            elif self._frame_size != (width, height):
                raise LiveFrameShapeError(
                    f"Frame size changed from {self._frame_size} to {(width, height)}."
                )

            assert self._first_timestamp is not None
            timeline_index = round(
                (float(packet.timestamp_sec) - self._first_timestamp) * self.expected_fps
            )
            if timeline_index <= self._last_timeline_index:
                raise LiveFrameTimestampError(
                    "Timestamp interval is shorter than the configured expected_fps slot."
                )

            assert self._frame_size is not None
            black_frame = np.zeros((height, width, 3), dtype=np.uint8)
            for _ in range(self._last_timeline_index + 1, timeline_index):
                self._writer.write(black_frame)
            self._writer.write(packet.frame)
            self._last_timeline_index = timeline_index
            self._last_timestamp = float(packet.timestamp_sec)
            self._received_frames += 1

    def finish(self) -> dict:
        """Close input, run the existing pipeline, and return Schema 1.2 dict."""
        with self._lock:
            self._ensure_open()
            if self._received_frames == 0:
                self._close_resources()
                raise EmptyLiveSessionError("At least one LIVE frame is required.")
            self._release_writer()
            self._closed = True

        try:
            return self.analyzer.analyze(
                video_path=self._video_path,
                **self.context.analyzer_arguments(),
            )
        finally:
            self._temp_dir.cleanup()

    def abort(self) -> None:
        """Stop an unfinished session and remove only its temporary video."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._close_resources()

    def _start_writer(self, width: int, height: int) -> None:
        self._frame_size = (width, height)
        writer = cv2.VideoWriter(
            str(self._video_path),
            cv2.VideoWriter_fourcc(*"MJPG"),
            self.expected_fps,
            self._frame_size,
        )
        if not writer.isOpened():
            writer.release()
            self._close_resources()
            raise LiveSessionError("Cannot create temporary LIVE video.")
        self._writer = writer

    def _release_writer(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def _close_resources(self) -> None:
        self._release_writer()
        self._closed = True
        self._temp_dir.cleanup()

    def _ensure_open(self) -> None:
        if self._closed:
            raise LiveSessionClosedError("LIVE session is already closed.")


class LivePetBehaviorAnalyzer:
    """Public factory used by a backend to open LIVE analysis sessions."""

    def __init__(
        self,
        analyzer: Optional[PetBehaviorAnalyzer] = None,
        temp_root: str | Path | None = None,
    ) -> None:
        self.analyzer = analyzer or PetBehaviorAnalyzer()
        self.temp_root = temp_root

    def start_session(
        self,
        *,
        context: AnalysisContext,
        expected_fps: float,
        max_gap_sec: float = 30.0,
    ) -> LiveAnalysisSession:
        return LiveAnalysisSession(
            context=context,
            analyzer=self.analyzer,
            expected_fps=expected_fps,
            temp_root=self.temp_root,
            max_gap_sec=max_gap_sec,
        )


__all__ = [
    "LivePetBehaviorAnalyzer",
    "LiveAnalysisSession",
    "LiveSessionError",
    "LiveSessionClosedError",
    "LiveFrameTimestampError",
    "LiveFrameShapeError",
    "EmptyLiveSessionError",
]
