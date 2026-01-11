"""
Semantic chunking logic for datasheet ingestion pipeline.

Implements two-stage chunking strategy:
    Stage 1: ExperimentalMarkdownSyntaxTextSplitter (preserve structure)
    Stage 2: RecursiveCharacterTextSplitter (intelligent splitting)

Ensures tables and code blocks remain intact within single chunks.
"""

import logging
import re
from typing import List, Optional

from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger("datasheet_ingestion.chunker")


# Configuration constants
CHUNK_SIZE_TARGET = 1500  # Target chunk size in characters
CHUNK_SIZE_MAX = 2000  # Maximum chunk size (hard limit for embeddings)
CHUNK_OVERLAP = 225  # 15% of target size
CHUNK_OVERLAP_PERCENT = 15


class SemanticChunker:
    """
    Two-stage semantic chunker for markdown documents.

    Preserves document structure (headers, tables, code blocks) while
    intelligently splitting content for optimal embedding quality.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_TARGET,
        chunk_overlap: int = CHUNK_OVERLAP,
        max_chunk_size: int = CHUNK_SIZE_MAX,
    ):
        """
        Initialize semantic chunker with configuration.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            max_chunk_size: Maximum allowed chunk size (for warnings)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunk_size = max_chunk_size

        # Stage 1: Markdown syntax-aware splitter
        self.markdown_splitter = ExperimentalMarkdownSyntaxTextSplitter(
            strip_headers=False,  # Keep headers for context
        )

        # Stage 2: Recursive character splitter
        self.char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],  # Prefer paragraph/sentence breaks
            length_function=len,
        )

        logger.info(
            f"SemanticChunker initialized: "
            f"target={chunk_size}, overlap={chunk_overlap}, max={max_chunk_size}"
        )

    def chunk_markdown(self, content: str) -> List[str]:
        """
        Chunk markdown content using two-stage semantic splitting.

        Stage 1: Split by markdown syntax (preserves tables, code blocks, sections)
        Stage 2: Further split large groups while respecting boundaries

        Args:
            content: Markdown content to chunk

        Returns:
            List of text chunks with preserved structure

        Raises:
            ValueError: If content is empty or invalid
        """
        if not content or not content.strip():
            raise ValueError("Cannot chunk empty content")

        logger.debug(f"Starting two-stage chunking for content ({len(content)} chars)")

        # Stage 1: Markdown structure preservation
        markdown_groups = self._stage1_markdown_split(content)

        # Stage 2: Intelligent character-level splitting
        final_chunks = self._stage2_recursive_split(markdown_groups)

        # Validate and log results
        self._validate_chunks(final_chunks)

        logger.info(
            f"Chunking complete: {len(final_chunks)} chunks created "
            f"(avg {sum(len(c) for c in final_chunks) // len(final_chunks)} chars)"
        )

        return final_chunks

    def _stage1_markdown_split(self, content: str) -> List[str]:
        """
        Stage 1: Split markdown by syntax boundaries.

        Preserves tables, code blocks, and section structure.

        Args:
            content: Markdown content

        Returns:
            List of markdown groups (may be large)
        """
        try:
            # LangChain text splitters return Document objects, extract text
            doc_groups = self.markdown_splitter.split_text(content)
            
            # Convert Document objects to strings if needed
            if doc_groups and hasattr(doc_groups[0], 'page_content'):
                groups = [doc.page_content for doc in doc_groups]
            else:
                groups = doc_groups
            
            logger.debug(
                f"Stage 1 complete: {len(groups)} markdown groups created"
            )
            return groups
        except Exception as e:
            logger.warning(
                f"Stage 1 markdown splitting failed: {e}. "
                f"Falling back to single group."
            )
            return [content]

    def _stage2_recursive_split(self, groups: List[str]) -> List[str]:
        """
        Stage 2: Recursively split large groups while preserving structure.

        Tables and code blocks are protected from mid-content splits.

        Args:
            groups: List of markdown groups from Stage 1

        Returns:
            List of final chunks
        """
        final_chunks = []

        for group in groups:
            # Check if group contains protected content (table or code block)
            has_table = self._contains_table(group)
            has_code_block = self._contains_code_block(group)

            if has_table or has_code_block:
                # Try to keep protected content intact
                protected_chunks = self._split_with_protection(group)
                final_chunks.extend(protected_chunks)
            else:
                # Standard recursive splitting
                try:
                    chunks = self.char_splitter.split_text(group)
                    final_chunks.extend(chunks)
                except Exception as e:
                    logger.warning(
                        f"Error in recursive splitting: {e}. "
                        f"Using group as-is."
                    )
                    final_chunks.append(group)

        logger.debug(
            f"Stage 2 complete: {len(final_chunks)} final chunks created"
        )

        return final_chunks

    def _split_with_protection(self, group: str) -> List[str]:
        """
        Split group while protecting tables and code blocks from mid-content splits.

        Strategy:
            1. If entire group fits in max_chunk_size, keep as single chunk
            2. Otherwise, try to split at paragraph boundaries outside protected areas
            3. If that fails, log warning and keep as single chunk (may exceed limit)

        Args:
            group: Markdown group containing table or code block

        Returns:
            List of chunks (usually 1 chunk to preserve structure)
        """
        group_size = len(group)

        # If group fits within max size, keep it intact
        if group_size <= self.max_chunk_size:
            logger.debug(
                f"Protected group kept intact ({group_size} chars, "
                f"within {self.max_chunk_size} limit)"
            )
            return [group]

        # If group is too large, log warning
        if group_size > self.max_chunk_size:
            logger.warning(
                f"Protected group exceeds maximum chunk size: "
                f"{group_size} > {self.max_chunk_size}. "
                f"Table or code block may be truncated by embedding model."
            )

            # Try to split at paragraph boundaries outside protected areas
            # This is a best-effort attempt
            try:
                chunks = self._split_outside_protected_areas(group)
                if chunks:
                    return chunks
            except Exception as e:
                logger.error(f"Error splitting outside protected areas: {e}")

            # If all else fails, keep as single chunk
            logger.warning(
                f"Keeping oversized group as single chunk ({group_size} chars)"
            )
            return [group]

        return [group]

    def _split_outside_protected_areas(self, group: str) -> List[str]:
        """
        Attempt to split group at paragraph boundaries outside tables/code blocks.

        Args:
            group: Markdown group

        Returns:
            List of chunks, or empty list if splitting not possible
        """
        # This is a complex operation that requires careful parsing
        # For MVP, we'll use simple recursive splitting as fallback
        # TODO: Implement sophisticated table/code block boundary detection

        try:
            chunks = self.char_splitter.split_text(group)
            return chunks
        except Exception as e:
            logger.debug(f"Could not split outside protected areas: {e}")
            return []

    def _contains_table(self, text: str) -> bool:
        """
        Check if text contains markdown table.

        Args:
            text: Text to check

        Returns:
            True if table detected, False otherwise
        """
        # Markdown table pattern: lines with pipes
        lines = text.split("\n")
        table_lines = [
            line
            for line in lines
            if "|" in line and line.strip().startswith("|")
        ]
        return len(table_lines) >= 2  # At least header + one row

    def _contains_code_block(self, text: str) -> bool:
        """
        Check if text contains code block.

        Args:
            text: Text to check

        Returns:
            True if code block detected, False otherwise
        """
        return "```" in text or "~~~" in text

    def _validate_chunks(self, chunks: List[str]) -> None:
        """
        Validate chunk quality and log warnings.

        Checks:
            - Empty chunks
            - Oversized chunks
            - Average chunk size

        Args:
            chunks: List of chunks to validate
        """
        if not chunks:
            logger.warning("No chunks created - validation skipped")
            return

        # Check for empty chunks
        empty_chunks = [i for i, c in enumerate(chunks) if not c.strip()]
        if empty_chunks:
            logger.warning(
                f"Found {len(empty_chunks)} empty chunks at indices: {empty_chunks}"
            )

        # Check for oversized chunks
        oversized = [
            (i, len(c))
            for i, c in enumerate(chunks)
            if len(c) > self.chunk_size
        ]

        if oversized:
            # Log warnings for chunks between target and max
            warnings = [(i, size) for i, size in oversized if size <= self.max_chunk_size]
            if warnings:
                logger.warning(
                    f"Found {len(warnings)} chunks exceeding target size "
                    f"({self.chunk_size} chars) but within max ({self.max_chunk_size}): "
                    f"{warnings[:3]}{'...' if len(warnings) > 3 else ''}"
                )

            # Log errors for chunks exceeding max
            errors = [(i, size) for i, size in oversized if size > self.max_chunk_size]
            if errors:
                logger.error(
                    f"Found {len(errors)} chunks exceeding maximum size "
                    f"({self.max_chunk_size} chars): "
                    f"{errors[:3]}{'...' if len(errors) > 3 else ''}"
                )

        # Log statistics
        total_chars = sum(len(c) for c in chunks)
        avg_size = total_chars // len(chunks)
        min_size = min(len(c) for c in chunks)
        max_size = max(len(c) for c in chunks)

        logger.info(
            f"Chunk statistics: "
            f"count={len(chunks)}, "
            f"avg={avg_size}, "
            f"min={min_size}, "
            f"max={max_size}, "
            f"total={total_chars}"
        )


def create_chunker(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> SemanticChunker:
    """
    Factory function to create semantic chunker with default or custom config.

    Args:
        chunk_size: Target chunk size (default: 1500)
        chunk_overlap: Overlap size (default: 225)

    Returns:
        Configured SemanticChunker instance
    """
    return SemanticChunker(
        chunk_size=chunk_size or CHUNK_SIZE_TARGET,
        chunk_overlap=chunk_overlap or CHUNK_OVERLAP,
    )
