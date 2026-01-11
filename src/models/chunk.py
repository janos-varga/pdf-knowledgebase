"""
Content chunk model for datasheet ingestion pipeline.

Contains:
    - ContentChunk: Semantically meaningful segment of a datasheet
"""

import re
from dataclasses import dataclass, field


@dataclass
class ContentChunk:
    """
    Represents a semantically meaningful segment of a datasheet.

    Attributes:
        text: Chunk text content
        datasheet_name: Parent datasheet identifier
        folder_path: Parent datasheet folder path
        chunk_index: Sequential position within datasheet
        ingestion_timestamp: ISO 8601 timestamp
        has_table: Flag indicating table presence
        has_code_block: Flag indicating code block presence
        section_heading: Markdown section heading (if available)
        image_paths: Absolute paths to images referenced in chunk
        source_page_hint: Approximate page number (future)
    """

    text: str
    datasheet_name: str
    folder_path: str
    chunk_index: int
    ingestion_timestamp: str
    has_table: bool = False
    has_code_block: bool = False
    section_heading: str | None = None
    image_paths: list[str] = field(default_factory=list)
    source_page_hint: int | None = None

    def __post_init__(self):
        """Validate chunk attributes and auto-detect metadata."""
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Chunk text cannot be empty")

        # Note: Removed hard chunk size limit. Embedding model will truncate if needed.
        # Tables should remain intact even if they exceed embedding model limits.

        if self.chunk_index < 0:
            raise ValueError("Chunk index must be non-negative")

        # Auto-detect table presence
        self.has_table = self._contains_table()

        # Auto-detect code block presence
        self.has_code_block = self._contains_code_block()

        # Extract section heading if not provided
        if self.section_heading is None:
            self.section_heading = self._extract_section_heading()

    def _contains_table(self) -> bool:
        """
        Check if chunk contains markdown table.

        Returns:
            True if markdown table detected
        """
        # Markdown table pattern: lines with pipes
        lines = self.text.split("\n")
        table_lines = [
            line for line in lines if "|" in line and line.strip().startswith("|")
        ]
        return len(table_lines) >= 2  # At least header + one row

    def _contains_code_block(self) -> bool:
        """
        Check if chunk contains code block.

        Returns:
            True if code block detected
        """
        return "```" in self.text or "~~~" in self.text

    def _extract_section_heading(self) -> str | None:
        """
        Extract first markdown heading from chunk.

        Returns:
            Section heading text (without markdown syntax), or None
        """
        lines = self.text.split("\n")
        for line in lines:
            if line.strip().startswith("#"):
                # Remove markdown heading syntax
                heading = re.sub(r"^#+\s*", "", line.strip())
                return heading[:100]  # Limit heading length
        return None

    def to_chromadb_format(self) -> tuple[str, dict]:
        """
        Convert chunk to ChromaDB format.

        Returns:
            Tuple of (document_text, metadata)
        """
        metadata = {
            "datasheet_name": self.datasheet_name,
            "folder_path": self.folder_path,
            "chunk_index": self.chunk_index,
            "ingestion_timestamp": self.ingestion_timestamp,
            "has_table": self.has_table,
            "has_code_block": self.has_code_block,
        }

        if self.section_heading:
            metadata["section_heading"] = self.section_heading

        if self.image_paths:
            # ChromaDB only supports str, int, float, bool metadata
            # Convert list to comma-separated string
            metadata["image_paths"] = ",".join(self.image_paths)

        if self.source_page_hint:
            metadata["source_page_hint"] = self.source_page_hint

        return (self.text, metadata)
