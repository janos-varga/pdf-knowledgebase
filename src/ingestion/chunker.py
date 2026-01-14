"""
Semantic chunking logic for datasheet ingestion pipeline.

Implements two-stage chunking strategy:
    Stage 1: ExperimentalMarkdownSyntaxTextSplitter (preserve structure)
    Stage 2: RecursiveCharacterTextSplitter (intelligent splitting)

Ensures tables and code blocks remain intact within single chunks.
"""

import logging

import tiktoken
from chonkie import (
    Chunk,
    CodeChunker,
    MarkdownChef,
    OverlapRefinery,
    RecursiveRules,
    TableChunker,
)
from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger("datasheet_ingestion.chunker")

# Configuration constants
CHUNK_SIZE_TARGET = 1024  # Target chunk size in characters (hard limit)
CHUNK_OVERLAP = 100  # Overlap for context


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
    ):
        """
        Initialize semantic chunker with configuration.

        Args:
            chunk_size: Target chunk size in characters (hard limit)
            chunk_overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Stage 1: Markdown syntax-aware splitter
        self.markdown_splitter = ExperimentalMarkdownSyntaxTextSplitter(
            strip_headers=False,  # Keep headers for context
        )

        # Stage 2: Recursive character splitter
        enc_name = tiktoken.encoding_name_for_model("text-embedding-3-small")
        self.tokenizer = tiktoken.get_encoding(enc_name)
        self.char_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=enc_name,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],  # Prefer paragraph/sentence breaks
        )
        # We should count lengths in tokens, not characters
        self.len_fn = self.char_splitter._length_function

        logger.info(
            f"SemanticChunker initialized: "
            f"target={chunk_size}, overlap={chunk_overlap}"
        )

    def chunk_markdown(self, content: str) -> list[str]:
        """
        Chunk markdown content using two-stage semantic splitting.

        Stage 1: Split by markdown syntax (preserves tables, code blocks, sections)
        Stage 2: Further split large groups while respecting boundaries
        Stage 3: Chonkie Refinery to improve context retention

        Args:
            content: Markdown content to chunk

        Returns:
            List of text chunks with preserved structure

        Raises:
            ValueError: If content is empty or invalid
        """
        if not content or not content.strip():
            raise ValueError("Cannot chunk empty content")

        logger.debug(
            f"Starting two-stage chunking for content ({len(content)} chars), "
            f"{self.len_fn} tokens"
        )

        # Stage 1: Markdown structure preservation
        markdown_groups = self._stage1_markdown_split(content)

        # Stage 2: Intelligent character-level splitting
        split_chunks = self._stage2_recursive_split(markdown_groups)

        # Stage 3: use Chonkie OverlapRefinery for better context retention
        # Requires converting our chunks to Chonkie Chunks and back
        rec_rules = RecursiveRules.from_recipe("markdown")
        overlap_refinery = OverlapRefinery(
            tokenizer=self.tokenizer,
            context_size=self.chunk_size,
            mode="recursive",
            rules=rec_rules,
        )
        refined_chunks: list[Chunk] = overlap_refinery.refine(
            [
                Chunk(
                    text=c, start_index=0, end_index=len(c), token_count=self.len_fn(c)
                )
                for c in split_chunks
            ]
        )
        final_chunks = [c.text for c in refined_chunks]

        # Validate and log results
        self._validate_chunks(final_chunks)

        logger.info(
            f"Chunking complete: {len(final_chunks)} chunks created "
            f"(avg {sum(len(c) for c in final_chunks) // len(final_chunks)} chars), "
            f"(avg {sum(self.len_fn(c) for c in final_chunks) // len(final_chunks)} tokens)."
        )

        return final_chunks

    def _stage1_markdown_split(self, content: str) -> list[str]:
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
            if doc_groups and hasattr(doc_groups[0], "page_content"):
                groups = [doc.page_content for doc in doc_groups]
            else:
                groups = doc_groups

            logger.debug(f"Stage 1 complete: {len(groups)} markdown groups created")
            return groups
        except Exception as e:
            logger.warning(
                f"Stage 1 markdown splitting failed: {e}. Falling back to single group."
            )
            return [content]

    def _stage2_recursive_split(self, groups: list[str]) -> list[str]:
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
                        f"Error in recursive splitting: {e}. Using group as-is."
                    )
                    final_chunks.append(group)

        logger.debug(f"Stage 2 complete: {len(final_chunks)} final chunks created")

        return final_chunks

    def _split_with_protection(self, group: str) -> list[str]:
        """
        Split group while protecting tables and code blocks from mid-content splits.

        Strategy:
            1. If entire group fits in chunk_size, keep as single chunk
            2. Otherwise, try to split at paragraph boundaries outside protected areas
            3. If that fails, log warning and keep as single chunk (may exceed limit)

        Args:
            group: Markdown group containing table or code block

        Returns:
            List of chunks (usually 1 chunk to preserve structure)
        """
        group_size = self.len_fn(group)

        # If group fits within target size, keep it intact
        if group_size <= self.chunk_size:
            logger.debug(
                f"Protected group kept intact ({group_size} chars, "
                f"within {self.chunk_size} limit)"
            )
            return [group]

        # If group is too large
        # Use Chonkie's table chunker to attempt safe split
        if group_size > self.chunk_size:
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

    def _split_outside_protected_areas(self, group: str) -> list[str]:
        """
        Attempt to split group at paragraph boundaries outside tables/code blocks.

        Args:
            group: Markdown group

        Returns:
            List of chunks, or empty list if splitting not possible

        Note:
            Currently returns empty list to force fallback to keeping tables intact.
            The RecursiveCharacterTextSplitter cannot safely split tables without
            separating table captions from table data, which breaks semantic queries.
        """
        logger.info("Calling Chonkie tools to split table/code.")
        chunks = []

        # Use MarkdownChef to parse document to ensure we attend to tables and code blocks,
        # and preserve other elements.
        mc = MarkdownChef(tokenizer=self.tokenizer)
        mc_doc = mc.parse(group)

        # Table chunking is simply done by TableChunker
        tbl_chunker = TableChunker(tokenizer="row", chunk_size=3)
        chunked_doc = tbl_chunker.chunk_document(mc_doc)

        # Code block chunking requires special treatment because we want to
        # support multiple code blocks per chunked document, in multiple languages.
        # But CodeChunker doesn't take MarkdownCode as an input, only raw text, or
        # the whole MarkdownDocument, assuming all code blocks are in the same language.
        # However, MarkdownChef detects the language and records it per block.
        for code_block in chunked_doc.code:
            # Initialize CodeChunker for this code block's language.
            code_chunker = CodeChunker(
                tokenizer=self.tokenizer,
                chunk_size=CHUNK_SIZE_TARGET,
                language=code_block.language,
            )
            # Run the CodeChunker on the individual code block content.
            new_chunks: list[Chunk] = code_chunker.chunk(code_block.content)
            for new_chunk in new_chunks:
                chunked_doc.chunks.append(
                    Chunk(
                        text=new_chunk.text,
                        start_index=new_chunk.start_index + code_block.start_index,
                        end_index=new_chunk.end_index + code_block.start_index,
                        token_count=new_chunk.token_count,
                    ),
                )

        # MarkdownChef removes images from the text, so we need to add them back
        for image in chunked_doc.images:
            chunked_doc.chunks.append(
                Chunk(
                    text=f"![{image.alias}]({image.content})",
                    start_index=image.start_index,
                    end_index=image.end_index,
                    token_count=self.len_fn(image.markdown),
                ),
            )

        chunked_doc.chunks.sort(key=lambda x: x.start_index)

        # Lastly, extract the chunk texts and return them as our chunks
        for chunk in chunked_doc.chunks:
            chunks.append(chunk.text)

        return chunks

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
            line for line in lines if "|" in line and line.strip().startswith("|")
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

    def _validate_chunks(self, chunks: list[str]) -> None:
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
            (i, self.len_fn(c))
            for i, c in enumerate(chunks)
            if self.len_fn(c) > self.chunk_size
        ]

        if oversized:
            logger.error(
                f"Found {len(oversized)} chunks exceeding chunk size "
                f"({self.chunk_size} tokens): "
                f"{oversized[:3]}{'...' if len(oversized) > 3 else ''}"
            )

        # Log statistics
        total_tokens = sum(self.len_fn(c) for c in chunks)
        avg_size = total_tokens // len(chunks)
        min_size = min(self.len_fn(c) for c in chunks)
        max_size = max(self.len_fn(c) for c in chunks)

        logger.info(
            f"Chunk statistics: "
            f"count={len(chunks)}, "
            f"avg={avg_size}, "
            f"min={min_size}, "
            f"max={max_size}, "
            f"total={total_tokens}"
        )


def create_chunker(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
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
