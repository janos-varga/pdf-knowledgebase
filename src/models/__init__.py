"""
Domain models for datasheet ingestion pipeline.

Exports:
    - IngestionStatus: Enum for ingestion state
    - Datasheet: Datasheet entity
    - ContentChunk: Content chunk entity
    - IngestionResult: Single datasheet ingestion result
    - BatchIngestionReport: Batch ingestion summary
"""

from enum import Enum

from src.models.chunk import ContentChunk
from src.models.datasheet import BatchIngestionReport, Datasheet, IngestionResult


class IngestionStatus(Enum):
    """Status of datasheet ingestion process."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"

    def __str__(self) -> str:
        """Return the string value of the status."""
        return self.value


__all__ = [
    "IngestionStatus",
    "Datasheet",
    "ContentChunk",
    "IngestionResult",
    "BatchIngestionReport",
]
