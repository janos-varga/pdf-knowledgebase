"""
Main ingestion pipeline orchestrator for datasheet ingestion.

Coordinates:
    - Datasheet discovery (folder scanning)
    - Single datasheet ingestion (parse → chunk → embed → store)
    - Batch ingestion with error handling and progress logging
    - Performance tracking
"""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from src.ingestion.chroma_client import ChromaDBClient
from src.ingestion.chunker import create_chunker
from src.ingestion.markdown_parser import (
    extract_image_references,
    parse_markdown_file,
    resolve_all_image_paths,
)
from src.models import (
    BatchIngestionReport,
    ContentChunk,
    Datasheet,
    IngestionResult,
    IngestionStatus,
)

logger = logging.getLogger("datasheet_ingestion.pipeline")


# Performance target: 30 seconds per datasheet
PERFORMANCE_TARGET_SECONDS = 30.0
EMBEDDING_MODEL_TOKEN_LIMIT = 100000


def _filter_chunk_image_paths(
    chunk_text: str,
    all_resolved_images: list[Path],
) -> list[str]:
    """
    Filter resolved image paths to only those referenced in chunk text.

    Args:
        chunk_text: Text content of the chunk
        all_resolved_images: All resolved image paths for the datasheet

    Returns:
        List of absolute path strings for images referenced in this chunk
    """
    # Extract image references from chunk text
    image_refs = extract_image_references(chunk_text)

    if not image_refs:
        return []

    # Create mapping of image filename to resolved path
    # (handles both relative refs like "image.png" and absolute paths)
    filename_to_path = {path.name: path for path in all_resolved_images}

    # Also map full resolved path strings for absolute references
    pathstr_to_path = {str(path): path for path in all_resolved_images}

    chunk_images = []
    for ref in image_refs:
        # Try to match by filename first (most common case for relative refs)
        ref_path = Path(ref)
        if ref_path.name in filename_to_path:
            resolved = filename_to_path[ref_path.name]
            if str(resolved) not in chunk_images:
                chunk_images.append(str(resolved))
        # Try to match by full path for absolute references
        elif ref in pathstr_to_path:
            resolved = pathstr_to_path[ref]
            if str(resolved) not in chunk_images:
                chunk_images.append(str(resolved))

    return chunk_images


def discover_datasheets(folder_path: Path) -> list[Datasheet]:
    """
    Discover datasheets in folder by scanning for subfolders with .md files.

    Supports two modes:
    1. Multiple datasheets: folder_path contains subfolders, each with one .md file
    2. Single datasheet: folder_path itself contains one .md file

    Expected structures:
        Multiple datasheets:
            folder_path/
                ├── Datasheet1/
                │   └── Datasheet1.md
                ├── Datasheet2/
                │   └── Datasheet2.md
                └── ...

        Single datasheet:
            folder_path/
                ├── Datasheet.md
                └── images/...

    Args:
        folder_path: Path to folder containing datasheet(s)

    Returns:
        List of discovered Datasheet instances

    Raises:
        ValueError: If folder_path is invalid
        FileNotFoundError: If folder_path does not exist
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")

    if not folder_path.is_dir():
        raise ValueError(f"Path is not a directory: {folder_path}")

    logger.info(f"Discovering datasheets in: {folder_path}")

    # Check if this is a single datasheet folder (has .md file directly)
    md_files = list(folder_path.glob("*.md"))
    if md_files:
        logger.info(
            f"Detected single datasheet folder with {len(md_files)} .md file(s)"
        )
        try:
            datasheet = Datasheet.from_folder(
                folder_path,
                ingestion_timestamp=datetime.now(UTC),
            )
            logger.info(f"Discovered single datasheet: {datasheet.name}")
            return [datasheet]
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to create datasheet from folder: {e}")
            return []

    # Otherwise, scan subfolders for datasheets
    datasheets = []
    subfolders = [p for p in folder_path.iterdir() if p.is_dir()]

    for subfolder in subfolders:
        try:
            # Try to create Datasheet from subfolder
            datasheet = Datasheet.from_folder(
                subfolder,
                ingestion_timestamp=datetime.now(UTC),
            )
            datasheets.append(datasheet)
            logger.debug(f"Discovered datasheet: {datasheet.name}")

        except FileNotFoundError as e:
            logger.warning(f"Skipping folder '{subfolder.name}': {e}")
        except ValueError as e:
            logger.warning(f"Skipping folder '{subfolder.name}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error discovering '{subfolder.name}': {e}")

    logger.info(f"Discovered {len(datasheets)} datasheets in {folder_path}")

    return datasheets


def _check_duplicate_datasheet(
    datasheet_name: str,
    chroma_client: ChromaDBClient,
    force_update: bool,
) -> tuple[bool, int]:
    """
    Check if datasheet exists and handle force_update logic.

    Args:
        datasheet_name: Name of the datasheet
        chroma_client: ChromaDB client
        force_update: Whether to delete existing chunks

    Returns:
        Tuple of (should_skip, deleted_count)
    """
    exists = chroma_client.datasheet_exists(datasheet_name)

    if not force_update and exists:
        logger.info(f"Datasheet already exists, skipping: {datasheet_name}")
        return True, 0

    if force_update and exists:
        logger.info(f"Force update: deleting existing chunks for {datasheet_name}")
        deleted_count = chroma_client.delete_datasheet(datasheet_name)
        logger.info(f"Deleted {deleted_count} existing chunks")
        return False, deleted_count

    return False, 0


def _parse_and_resolve_content(
    datasheet: Datasheet,
) -> tuple[str, list[Path]]:
    """
    Parse markdown and resolve image paths.

    Args:
        datasheet: Datasheet to process

    Returns:
        Tuple of (content, resolved_images)
    """
    logger.debug(f"Parsing markdown: {datasheet.markdown_file_path}")
    content = parse_markdown_file(datasheet.markdown_file_path)

    logger.debug(f"Resolving image paths for: {datasheet.name}")
    content, resolved_images = resolve_all_image_paths(
        content,
        datasheet.markdown_file_path,
    )

    return content, resolved_images


def _create_text_chunks(
    content: str,
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> list[str]:
    """
    Chunk markdown content.

    Args:
        content: Markdown content to chunk
        chunk_size: Target chunk size in tokens
        chunk_overlap: Chunk overlap in tokens

    Returns:
        List of text chunks
    """
    logger.debug("Chunking content")
    chunker = create_chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk_markdown(content)


def _build_content_chunks(
    text_chunks: list[str],
    datasheet: Datasheet,
    resolved_images: list[Path],
) -> list[ContentChunk]:
    """
    Create ContentChunk instances from text chunks.

    Args:
        text_chunks: List of text chunks
        datasheet: Source datasheet
        resolved_images: All resolved image paths

    Returns:
        List of ContentChunk instances
    """
    logger.debug(f"Creating {len(text_chunks)} ContentChunk instances")
    chunks = []

    for idx, text in enumerate(text_chunks):
        chunk_image_paths = _filter_chunk_image_paths(text, resolved_images)

        chunk = ContentChunk(
            text=text,
            datasheet_name=datasheet.name,
            folder_path=str(datasheet.folder_path),
            chunk_index=idx,
            ingestion_timestamp=datasheet.ingestion_timestamp.isoformat() + "Z",
            image_paths=chunk_image_paths,
        )
        chunks.append(chunk)

    return chunks


def _insert_chunks_with_batching(
    chunks: list[ContentChunk],
    chroma_client: ChromaDBClient,
) -> tuple[int, int]:
    """
    Insert chunks into ChromaDB with automatic batching for large datasheets.

    Args:
        chunks: List of chunks to insert
        chroma_client: ChromaDB client

    Returns:
        Tuple of (inserted_chunks, inserted_token_count)
    """
    total_tokens = sum(chunk.token_count for chunk in chunks)

    if total_tokens > EMBEDDING_MODEL_TOKEN_LIMIT:
        logger.debug(
            "Large datasheet detected, inserting in batches to avoid API overload"
        )
        return _insert_chunks_in_batches(chunks, chroma_client)
    else:
        logger.debug(f"Inserting {len(chunks)} chunks into ChromaDB")
        inserted_chunks = chroma_client.insert_chunks(chunks)
        inserted_token_count = sum(chunk.token_count for chunk in chunks)
        return inserted_chunks, inserted_token_count


def _insert_chunks_in_batches(
    chunks: list[ContentChunk],
    chroma_client: ChromaDBClient,
) -> tuple[int, int]:
    """
    Insert chunks in batches to respect embedding model token limits.

    Args:
        chunks: List of chunks to insert
        chroma_client: ChromaDB client

    Returns:
        Tuple of (inserted_chunks, inserted_token_count)
    """
    batch = []
    current_batch_token_count = 0
    inserted_chunks = 0
    inserted_token_count = 0

    for chunk in chunks:
        if (
            current_batch_token_count + chunk.token_count
            > EMBEDDING_MODEL_TOKEN_LIMIT
        ):
            logger.debug(f"Inserting batch of {len(batch)} chunks into ChromaDB")
            inserted_chunks += chroma_client.insert_chunks(batch)
            inserted_token_count += sum(c.token_count for c in batch)

            batch = [chunk]
            current_batch_token_count = chunk.token_count
        else:
            batch.append(chunk)
            current_batch_token_count += chunk.token_count

    if batch:
        logger.debug(f"Inserting final batch of {len(batch)} chunks into ChromaDB")
        inserted_chunks += chroma_client.insert_chunks(batch)
        inserted_token_count += sum(c.token_count for c in batch)

    logger.debug(f"Total inserted tokens: {inserted_token_count}")
    return inserted_chunks, inserted_token_count


def _update_datasheet_status(
    datasheet: Datasheet,
    inserted_chunks: int,
    inserted_token_count: int,
    duration: float,
) -> None:
    """
    Update datasheet with ingestion results.

    Args:
        datasheet: Datasheet to update
        inserted_chunks: Number of chunks inserted
        inserted_token_count: Total token count
        duration: Ingestion duration in seconds
    """
    datasheet.status = IngestionStatus.SUCCESS
    datasheet.chunk_count = inserted_chunks
    datasheet.token_count = inserted_token_count
    datasheet.duration_seconds = duration


def _log_completion(
    datasheet_name: str,
    chunk_count: int,
    token_count: int,
    duration: float,
) -> None:
    """
    Log ingestion completion with performance metrics.

    Args:
        datasheet_name: Name of the datasheet
        chunk_count: Number of chunks created
        token_count: Total token count
        duration: Ingestion duration in seconds
    """
    if duration > PERFORMANCE_TARGET_SECONDS:
        logger.warning(
            f"[!] Ingestion exceeded {PERFORMANCE_TARGET_SECONDS}s target: "
            f"{datasheet_name} took {duration:.2f}s"
        )
    else:
        logger.info(
            f"[OK] Ingestion complete: {datasheet_name} "
            f"{chunk_count} chunks, {token_count} tokens, {duration:.2f}s)"
        )

    logger.info("-" * 70)


def ingest_datasheet(
    datasheet: Datasheet,
    chroma_client: ChromaDBClient,
    force_update: bool = False,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> IngestionResult:
    """
    Ingest single datasheet: parse → chunk → embed → store.

    Orchestrates the complete ingestion pipeline for one datasheet.

    Args:
        datasheet: Datasheet instance to ingest
        chroma_client: ChromaDB client for storage
        force_update: If True, delete existing chunks before re-ingestion
        chunk_size: Target chunk size in tokens (default: None, uses chunker default)
        chunk_overlap: Chunk overlap in tokens (default: None, uses chunker default)

    Returns:
        IngestionResult with status and metrics

    Raises:
        RuntimeError: If ingestion fails critically
    """
    start_time = time.time()
    datasheet.status = IngestionStatus.PROCESSING

    logger.info(f"Starting ingestion: {datasheet.name}")

    try:
        should_skip, _ = _check_duplicate_datasheet(
            datasheet.name, chroma_client, force_update
        )

        if should_skip:
            duration = time.time() - start_time
            logger.info("-" * 70)
            return IngestionResult(
                datasheet_name=datasheet.name,
                status=IngestionStatus.SKIPPED,
                duration_seconds=duration,
                skipped_reason="Datasheet already exists in ChromaDB (use --force-update to overwrite)",
            )

        # Parse and resolve content
        content, resolved_images = _parse_and_resolve_content(datasheet)

        # Chunk content
        text_chunks = _create_text_chunks(content, chunk_size, chunk_overlap)
        chunks = _build_content_chunks(text_chunks, datasheet, resolved_images)

        # Insert chunks into ChromaDB with batching if needed
        inserted_chunks, inserted_token_count = _insert_chunks_with_batching(
            chunks, chroma_client
        )

        duration = time.time() - start_time
        _update_datasheet_status(
            datasheet, inserted_chunks, inserted_token_count, duration
        )
        _log_completion(datasheet.name, len(chunks), inserted_token_count, duration)

        return IngestionResult(
            datasheet_name=datasheet.name,
            status=IngestionStatus.SUCCESS,
            duration_seconds=duration,
            chunks_created=inserted_chunks,
            tokens_inserted=inserted_token_count,
        )

    except Exception as e:
        duration = time.time() - start_time
        datasheet.status = IngestionStatus.ERROR
        datasheet.error_message = str(e)
        datasheet.duration_seconds = duration

        logger.error(
            f"[X] Ingestion failed: {datasheet.name} - {e}",
            exc_info=True,
        )
        logger.info("-" * 70)

        return IngestionResult(
            datasheet_name=datasheet.name,
            status=IngestionStatus.ERROR,
            duration_seconds=duration,
            error_message=str(e),
        )


def ingest_batch(
    datasheets: list[Datasheet],
    chroma_client: ChromaDBClient,
    force_update: bool = False,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> BatchIngestionReport:
    """
    Ingest batch of datasheets with error handling and progress logging.

    Processes each datasheet independently - one failure doesn't stop the batch.

    Args:
        datasheets: List of datasheets to ingest
        chroma_client: ChromaDB client for storage
        force_update: If True, delete existing chunks before re-ingestion
        chunk_size: Target chunk size in tokens (default: None, uses chunker default)
        chunk_overlap: Chunk overlap in tokens (default: None, uses chunker default)

    Returns:
        BatchIngestionReport with summary and per-datasheet results

    Raises:
        RuntimeError: If ChromaDB connection fails (batch-level error)
    """
    start_timestamp = datetime.now(UTC)
    logger.info(f"Starting batch ingestion: {len(datasheets)} datasheets")

    # Validate ChromaDB connection
    is_valid, error_msg = chroma_client.validate_connection()
    if not is_valid:
        raise RuntimeError(f"ChromaDB connection validation failed: {error_msg}")

    results = []

    # Process each datasheet
    for i, datasheet in enumerate(datasheets, start=1):
        logger.info(f"[{i}/{len(datasheets)}] Processing: {datasheet.name}")

        try:
            result = ingest_datasheet(
                datasheet, chroma_client, force_update, chunk_size, chunk_overlap
            )
            results.append(result)

            # Log progress
            if result.is_success():
                logger.info(
                    f"  [OK] Success: {result.chunks_created} chunks, "
                    f"{result.tokens_inserted} tokens, "
                    f"{result.duration_seconds:.2f}s"
                )
            elif result.is_skipped():
                logger.info(f"  [>>] Skipped: {result.skipped_reason}")
            elif result.is_error():
                logger.error(f"  [X] Failed: {result.error_message}")

        except Exception as e:
            # Catch unexpected exceptions at batch level
            logger.error(
                f"  [X] Unexpected error processing {datasheet.name}: {e}",
                exc_info=True,
            )

            # Create error result
            result = IngestionResult(
                datasheet_name=datasheet.name,
                status=IngestionStatus.ERROR,
                duration_seconds=0.0,
                error_message=f"Unexpected error: {e}",
            )
            results.append(result)

    end_timestamp = datetime.now(UTC)

    # Create batch report
    report = BatchIngestionReport(
        results=results,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )

    logger.info("Batch ingestion complete")
    logger.info(f"  Total: {report.total_datasheets}")
    logger.info(f"  [OK] Successful: {report.successful}")
    logger.info(f"  [>>] Skipped: {report.skipped}")
    logger.info(f"  [X] Failed: {report.failed}")
    logger.info(f"  Duration: {report.total_duration_seconds:.2f}s")

    return report


def track_performance(result: IngestionResult) -> None:
    """
    Track and log performance metrics for ingestion result.

    Args:
        result: Ingestion result to track
    """
    if not result.is_success():
        return

    duration = result.duration_seconds
    chunks = result.chunks_created or 0

    # Log performance metrics
    logger.info(
        f"Performance metrics for {result.datasheet_name}: "
        f"duration={duration:.2f}s, "
        f"chunks={chunks}, "
        f"chunks_per_second={chunks / duration if duration > 0 else 0:.2f}"
    )

    # Warn if exceeded target
    if duration > PERFORMANCE_TARGET_SECONDS:
        logger.warning(
            f"[!] Performance target exceeded: "
            f"{duration:.2f}s > {PERFORMANCE_TARGET_SECONDS}s target "
            f"for {result.datasheet_name}"
        )
