"""Public Python interface for the existing pet behavior pipeline."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from jsonschema import Draft202012Validator, FormatChecker

try:
    from .roi_models import RoiRequest, RoiValidationError, parse_roi_request
except ImportError:  # Direct execution with src on sys.path.
    from roi_models import RoiRequest, RoiValidationError, parse_roi_request


IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
ALLOWED_RECORDED_AT_SOURCES = {"CAMERA", "FILE_METADATA", "REQUEST_TIME"}
_ANALYSIS_LOCK = threading.Lock()


class PetBehaviorAnalyzerError(RuntimeError):
    """Base error raised by the public analyzer interface."""


class AnalyzerInputError(PetBehaviorAnalyzerError, ValueError):
    """The caller supplied an invalid argument."""


class AnalysisConflictError(PetBehaviorAnalyzerError):
    """An analysis_id already belongs to a different request."""


class PipelineExecutionError(PetBehaviorAnalyzerError):
    """The pipeline did not produce a readable result artifact."""


class ResultReadError(PetBehaviorAnalyzerError):
    """The result artifact could not be read as JSON."""


class ResultIdentityMismatchError(PetBehaviorAnalyzerError):
    """The generated result does not belong to the submitted request."""


class ResultSchemaError(PetBehaviorAnalyzerError):
    """The generated result does not satisfy Schema 1.2."""


class PetBehaviorAnalyzer:
    """Run the validated CLI pipeline and return its Schema 1.2 result."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        self.base_dir = (
            Path(base_dir).resolve()
            if base_dir is not None
            else Path(__file__).resolve().parent.parent
        )
        self.python_executable = str(python_executable or sys.executable)
        self.pipeline_script = self.base_dir / "src" / "run_pipeline.py"
        self.result_dir = self.base_dir / "data" / "outputs" / "analysis_results"
        self.schema_path = self.base_dir / "schemas" / "analysis_result_v1.2.schema.json"

    def analyze(
        self,
        *,
        video_path: str | Path,
        analysis_id: str,
        pet_id: str,
        video_id: str,
        camera_id: str,
        species: str,
        recorded_at: str,
        recorded_at_source: str = "REQUEST_TIME",
        time_slot: Optional[str] = None,
        roi_data: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        """Execute run_pipeline.py and return the generated result dictionary.

        A pipeline-level FAILED result is returned normally. Exceptions are
        reserved for invalid interface arguments, conflicts, or infrastructure
        failures where no trustworthy Schema 1.2 result can be returned.
        """
        request = self._normalize_request(
            video_path=video_path,
            analysis_id=analysis_id,
            pet_id=pet_id,
            video_id=video_id,
            camera_id=camera_id,
            species=species,
            recorded_at=recorded_at,
            recorded_at_source=recorded_at_source,
            time_slot=time_slot,
            roi_data=roi_data,
        )
        result_path = self.result_dir / f"{request['analysis_id']}_result.json"

        with _ANALYSIS_LOCK:
            existing = self._load_existing_if_compatible(result_path, request)
            if existing is not None:
                return existing
            return self._execute_pipeline(request, result_path)

    def analyze_precomputed(
        self,
        *,
        video_path: str | Path,
        precomputed_artifacts: Mapping[str, Any],
        analysis_id: str,
        pet_id: str,
        video_id: str,
        camera_id: str,
        species: str,
        recorded_at: str,
        recorded_at_source: str = "REQUEST_TIME",
        time_slot: Optional[str] = None,
        roi_data: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        """Finalize a LIVE session without running YOLO or feature extraction again."""
        request = self._normalize_request(
            video_path=video_path, analysis_id=analysis_id, pet_id=pet_id,
            video_id=video_id, camera_id=camera_id, species=species,
            recorded_at=recorded_at, recorded_at_source=recorded_at_source,
            time_slot=time_slot, roi_data=roi_data,
        )
        result_path = self.result_dir / f"{request['analysis_id']}_result.json"
        stem = request["video_path"].stem
        output_dir = self.base_dir / "data" / "outputs"
        destinations = {
            "tracking": output_dir / f"{stem}_tracking.csv",
            "quality": output_dir / f"{stem}_tracking_quality.csv",
            "features": output_dir / f"{stem}_features.csv",
            "interval_features": output_dir / f"{stem}_features_by_interval.csv",
        }
        with _ANALYSIS_LOCK:
            existing = self._load_existing_if_compatible(result_path, request)
            if existing is not None:
                return existing
            output_dir.mkdir(parents=True, exist_ok=True)
            for key, destination in destinations.items():
                source = Path(precomputed_artifacts[key])
                if not source.is_file():
                    raise PipelineExecutionError(f"Missing precomputed LIVE artifact: {source}")
                shutil.copy2(source, destination)
            return self._execute_pipeline(request, result_path, precomputed_live=True)

    def _normalize_request(self, **values: Any) -> dict:
        for required_path in (self.pipeline_script, self.schema_path):
            if not required_path.is_file():
                raise PipelineExecutionError(f"Required model file not found: {required_path}")

        for field_name in ("analysis_id", "pet_id", "video_id", "camera_id"):
            normalized = str(values[field_name]).strip()
            if not IDENTIFIER_PATTERN.fullmatch(normalized):
                raise AnalyzerInputError(
                    f"{field_name} must start with an alphanumeric character, contain only "
                    "letters, numbers, '.', '_' or '-', and be at most 128 characters."
                )
            values[field_name] = normalized

        species = str(values["species"]).strip().upper()
        if species not in {"CAT", "DOG"}:
            raise AnalyzerInputError("species must be CAT or DOG.")
        values["species"] = species

        source = str(values["recorded_at_source"]).strip().upper()
        if source not in ALLOWED_RECORDED_AT_SOURCES:
            raise AnalyzerInputError(
                "recorded_at_source must be CAMERA, FILE_METADATA or REQUEST_TIME."
            )
        values["recorded_at_source"] = source

        recorded_at = str(values["recorded_at"]).strip()
        try:
            parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise AnalyzerInputError("recorded_at must be ISO 8601.") from error
        if parsed.tzinfo is None:
            raise AnalyzerInputError("recorded_at must include a timezone.")
        values["recorded_at"] = parsed.isoformat(timespec="seconds")

        if values["time_slot"] is not None:
            slot = str(values["time_slot"]).strip()
            match = re.fullmatch(r"([01]\d|2[0-3]):00-([01]\d|2[0-3]):00", slot)
            if match is None or int(match.group(2)) != (int(match.group(1)) + 1) % 24:
                raise AnalyzerInputError("time_slot must be a consecutive one-hour slot.")
            values["time_slot"] = slot

        raw_path = Path(values["video_path"]).expanduser()
        values["video_path"] = (
            (self.base_dir / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
        )

        try:
            values["roi_request"] = parse_roi_request(
                values.pop("roi_data"),
                expected_camera_id=values["camera_id"],
            )
        except RoiValidationError as error:
            raise AnalyzerInputError(f"Invalid ROI request: {error}") from error
        return values

    def _execute_pipeline(self, request: dict, result_path: Path, precomputed_live: bool = False) -> dict:
        roi_path: Optional[Path] = None
        command = [
            self.python_executable,
            str(self.pipeline_script),
            str(request["video_path"]),
            request["species"].lower(),
            "--analysis-id", request["analysis_id"],
            "--pet-id", request["pet_id"],
            "--video-id", request["video_id"],
            "--camera-id", request["camera_id"],
            "--recorded-at", request["recorded_at"],
            "--recorded-at-source", request["recorded_at_source"],
        ]
        if request["time_slot"]:
            command.extend(["--time-slot", request["time_slot"]])
        if precomputed_live:
            command.append("--precomputed-live")

        try:
            roi_request: RoiRequest | None = request["roi_request"]
            if roi_request is not None:
                self.result_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix="_roi_request.json",
                    prefix=f"{request['analysis_id']}_",
                    dir=self.result_dir,
                    encoding="utf-8",
                    delete=False,
                ) as roi_file:
                    json.dump(
                        {
                            "camera_id": roi_request.camera_id,
                            "roi_areas": [area.to_dict() for area in roi_request.roi_areas],
                        },
                        roi_file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    roi_path = Path(roi_file.name)
                command.extend(["--roi-request-json", str(roi_path)])

            try:
                completed = subprocess.run(
                    command,
                    cwd=self.base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            except OSError as error:
                raise PipelineExecutionError(f"Cannot start pipeline process: {error}") from error
            if not result_path.is_file():
                raise PipelineExecutionError(
                    "Pipeline did not create a result JSON "
                    f"(return_code={completed.returncode}): {completed.stdout[-4000:]}"
                )
            result = self._load_result(result_path)
            self._validate_result(result, request)
            return result
        finally:
            if roi_path is not None:
                roi_path.unlink(missing_ok=True)

    def _load_existing_if_compatible(self, result_path: Path, request: dict) -> dict | None:
        if not result_path.is_file():
            return None
        result = self._load_result(result_path)
        mismatches = self._request_mismatches(result, request)
        if mismatches:
            raise AnalysisConflictError(
                "analysis_id already exists for a different request: " + "; ".join(mismatches)
            )
        self._validate_schema(result)
        return result

    def _load_result(self, result_path: Path) -> dict:
        try:
            with result_path.open("r", encoding="utf-8-sig") as result_file:
                result = json.load(result_file)
        except (OSError, json.JSONDecodeError) as error:
            raise ResultReadError(f"Cannot read result JSON: {result_path}: {error}") from error
        if not isinstance(result, dict):
            raise ResultReadError(f"Result JSON root must be an object: {result_path}")
        return result

    def _validate_result(self, result: dict, request: dict) -> None:
        mismatches = self._request_mismatches(result, request)
        if mismatches:
            raise ResultIdentityMismatchError("; ".join(mismatches))
        self._validate_schema(result)

    def _request_mismatches(self, result: dict, request: dict) -> list[str]:
        expected = {
            "analysis_id": request["analysis_id"],
            "pet_id": request["pet_id"],
            "video_id": request["video_id"],
            "camera_id": request["camera_id"],
            "species": request["species"],
            "recorded_at": request["recorded_at"],
            "recorded_at_source": request["recorded_at_source"],
        }
        if request["time_slot"] is not None:
            expected["time_slot"] = request["time_slot"]
        mismatches = [
            f"{key}: result={result.get(key)!r}, request={value!r}"
            for key, value in expected.items()
            if result.get(key) != value
        ]
        expected_roi = self._canonical_roi(request["roi_request"])
        actual_roi = self._result_roi(result)
        if actual_roi != expected_roi:
            mismatches.append("roi_areas differ")
        return mismatches

    @staticmethod
    def _canonical_roi(roi_request: RoiRequest | None) -> list[dict] | None:
        return None if roi_request is None else [area.to_dict() for area in roi_request.roi_areas]

    @staticmethod
    def _result_roi(result: dict) -> list[dict] | None:
        space = result.get("space_analysis")
        if not isinstance(space, dict) or not isinstance(space.get("roi_results"), list):
            return None
        keys = ("roi_id", "roi_name", "roi_type", "x", "y", "width", "height")
        return [
            {key: item.get(key) for key in keys}
            for item in space["roi_results"]
            if isinstance(item, dict)
        ]

    def _validate_schema(self, result: dict) -> None:
        try:
            with self.schema_path.open("r", encoding="utf-8-sig") as schema_file:
                schema = json.load(schema_file)
        except (OSError, json.JSONDecodeError) as error:
            raise ResultSchemaError(f"Cannot load Schema 1.2: {error}") from error
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            details = "; ".join(error.message for error in errors[:10])
            raise ResultSchemaError(f"Result failed Schema 1.2 validation: {details}")


__all__ = [
    "PetBehaviorAnalyzer",
    "PetBehaviorAnalyzerError",
    "AnalyzerInputError",
    "AnalysisConflictError",
    "PipelineExecutionError",
    "ResultReadError",
    "ResultIdentityMismatchError",
    "ResultSchemaError",
]
