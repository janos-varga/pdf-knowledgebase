"""
Datasheet domain models.

Contains:
    - Datasheet: Datasheet entity with validation
    - IngestionResult: Single datasheet ingestion result
    - BatchIngestionReport: Batch ingestion summary
"""
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.models.status import IngestionStatus


@dataclass
class Datasheet:
    """
    Represents a single electrical component's technical documentation.

    Attributes:
        name: Unique identifier derived from folder name
        folder_path: Absolute path to datasheet folder
        markdown_file_path: Absolute path to markdown file
        ingestion_timestamp: ISO 8601 timestamp when ingestion started
        status: Current ingestion state
        image_paths: List of absolute paths to images in folder
        component_type: Type of component (e.g., "op-amp", "microcontroller")
        error_message: Error details if status is "error"
        chunk_count: Number of chunks created (if successful)
        duration_seconds: Time taken for ingestion
    """

    name: str
    folder_path: Path
    markdown_file_path: Path
    ingestion_timestamp: datetime
    status: IngestionStatus
    image_paths: list[Path] = None
    component_type: str | None = None
    error_message: str | None = None
    chunk_count: int | None = None
    duration_seconds: float | None = None

    def __post_init__(self):
        """Validate datasheet attributes."""
        if not self.name:
            raise ValueError("Datasheet name cannot be empty")

        if not self.folder_path.exists():
            raise FileNotFoundError(f"Folder does not exist: {self.folder_path}")

        if not self.folder_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.folder_path}")

        if not self.markdown_file_path.exists():
            raise FileNotFoundError(
                f"Markdown file not found: {self.markdown_file_path}"
            )

        if self.markdown_file_path.suffix.lower() != ".md":
            raise ValueError(f"File is not markdown: {self.markdown_file_path}")

        if self.image_paths is None:
            self.image_paths = []

    @classmethod
    def from_folder(
        cls, folder_path: Path, ingestion_timestamp: datetime = None
    ) -> "Datasheet":
        """
        Create Datasheet from folder path.

        Expects folder structure:
            datasheets/
              └── TL072/
                  ├── TL072.md
                  ├── pinout.png
                  └── schematic.png

        Args:
            folder_path: Path to datasheet folder
            ingestion_timestamp: When ingestion started (default: now UTC)

        Returns:
            Datasheet instance

        Raises:
            FileNotFoundError: If no markdown file found
            ValueError: If multiple markdown files found
        """
        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.now(UTC)

        folder_path = folder_path.resolve()
        name = folder_path.name

        # Find markdown file (expect exactly one)
        md_files = list(folder_path.glob("*.md"))
        if len(md_files) == 0:
            raise FileNotFoundError(f"No markdown file found in {folder_path}")
        if len(md_files) > 1:
            raise ValueError(
                f"Multiple markdown files found in {folder_path}: {md_files}"
            )

        markdown_file_path = md_files[0]

        # Find all images (optional)
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp"}
        image_paths = [
            p
            for p in folder_path.rglob("*")
            if p.is_file() and p.suffix.lower() in image_extensions
        ]

        return cls(
            name=name,
            folder_path=folder_path,
            markdown_file_path=markdown_file_path,
            ingestion_timestamp=ingestion_timestamp,
            status=IngestionStatus.PENDING,
            image_paths=image_paths,
        )


@dataclass
class IngestionResult:
    """
    Represents the outcome of ingesting a single datasheet.

    Attributes:
        datasheet_name: Datasheet identifier
        status: Outcome (success/error/skipped)
        duration_seconds: Time taken for ingestion
        chunks_created: Number of chunks inserted (if successful)
        error_message: Error details (if status is error)
        skipped_reason: Reason for skipping (if status is skipped)
    """

    datasheet_name: str
    status: IngestionStatus
    duration_seconds: float
    chunks_created: int | None = None
    error_message: str | None = None
    skipped_reason: str | None = None

    def is_success(self) -> bool:
        """Check if ingestion was successful."""
        return self.status == IngestionStatus.SUCCESS

    def is_error(self) -> bool:
        """Check if ingestion failed with error."""
        return self.status == IngestionStatus.ERROR

    def is_skipped(self) -> bool:
        """Check if ingestion was skipped."""
        return self.status == IngestionStatus.SKIPPED

    def exceeded_performance_target(self) -> bool:
        """
        Check if ingestion exceeded 30-second target.

        Returns:
            True if duration > 30 seconds
        """
        return self.duration_seconds > 30.0

    def to_dict(self) -> dict:
        """
        Convert to dictionary for logging.

        Returns:
            Dictionary representation of result
        """
        result = {
            "datasheet_name": self.datasheet_name,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 2),
        }

        if self.chunks_created is not None:
            result["chunks_created"] = self.chunks_created

        if self.error_message:
            result["error_message"] = self.error_message

        if self.skipped_reason:
            result["skipped_reason"] = self.skipped_reason

        return result


@dataclass
class BatchIngestionReport:
    """
    Represents the summary of a complete ingestion batch.

    Attributes:
        results: Per-datasheet results
        start_timestamp: Batch start time
        end_timestamp: Batch end time
    """

    results: list[IngestionResult]
    start_timestamp: datetime
    end_timestamp: datetime

    @property
    def total_datasheets(self) -> int:
        """Total number of datasheets processed."""
        return len(self.results)

    @property
    def successful(self) -> int:
        """Number successfully ingested."""
        return sum(1 for r in self.results if r.is_success())

    @property
    def skipped(self) -> int:
        """Number skipped (already exist)."""
        return sum(1 for r in self.results if r.is_skipped())

    @property
    def failed(self) -> int:
        """Number failed with errors."""
        return sum(1 for r in self.results if r.is_error())

    @property
    def total_chunks(self) -> int:
        """Total chunks created across all successful ingestions."""
        return sum(r.chunks_created or 0 for r in self.results if r.chunks_created)

    @property
    def total_duration_seconds(self) -> float:
        """Total processing time for entire batch."""
        return (self.end_timestamp - self.start_timestamp).total_seconds()

    def success_rate(self) -> float:
        """
        Calculate success rate as percentage.

        Returns:
            Success rate (0-100)
        """
        if self.total_datasheets == 0:
            return 0.0
        return (self.successful / self.total_datasheets) * 100

    def exceeded_performance_targets(self) -> list[str]:
        """
        Return list of datasheets that exceeded 30-second target.

        Returns:
            List of datasheet names
        """
        return [
            r.datasheet_name
            for r in self.results
            if r.is_success() and r.exceeded_performance_target()
        ]

    def summary(self) -> str:
        """
        Generate human-readable summary.

        Returns:
            Formatted summary string
        """
        lines = [
            os.linesep,
            "=" * 60,
            "Ingestion Batch Summary",
            "=" * 60,
            f"Total Datasheets: {self.total_datasheets}",
            f"  [OK] Successful: {self.successful}",
            f"  [>>] Skipped: {self.skipped}",
            f"  [X] Failed: {self.failed}",
            "",
            f"Total Chunks Created: {self.total_chunks}",
            f"Total Duration: {self.total_duration_seconds:.2f} seconds",
            f"Success Rate: {self.success_rate():.1f}%",
        ]

        slow = self.exceeded_performance_targets()
        if slow:
            lines.append(f"[!] Slow Ingestions (>30s): {len(slow)}")
            for name in slow[:5]:  # Show first 5
                lines.append(f"  - {name}")
            if len(slow) > 5:
                lines.append(f"  ... and {len(slow) - 5} more")

        if self.failed > 0:
            lines.append("[X] Failed Datasheets:")
            for result in self.results:
                if result.is_error():
                    lines.append(f"  - {result.datasheet_name}: {result.error_message}")

        lines.append("=" * 60)
        return os.linesep.join(lines)
