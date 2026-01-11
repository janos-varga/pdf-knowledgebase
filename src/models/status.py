"""Ingestion status enumeration."""

from enum import Enum


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
