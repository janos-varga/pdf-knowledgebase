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


def discover_datasheets(folder_path: Path) -> list[Datasheet]:
    """
    Discover datasheets in folder by scanning for subfolders with .md files.

    Expected structure:
        folder_path/
            ├── Datasheet1/
            │   └── Datasheet1.md
            ├── Datasheet2/
            │   └── Datasheet2.md
            └── ...

    Args:
        folder_path: Path to folder containing datasheet subfolders

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


def ingest_datasheet(
    datasheet: Datasheet,
    chroma_client: ChromaDBClient,
    force_update: bool = False,
) -> IngestionResult:
    """
    Ingest single datasheet: parse → chunk → embed → store.

    Orchestrates the complete ingestion pipeline for one datasheet.

    Args:
        datasheet: Datasheet instance to ingest
        chroma_client: ChromaDB client for storage
        force_update: If True, delete existing chunks before re-ingestion

    Returns:
        IngestionResult with status and metrics

    Raises:
        RuntimeError: If ingestion fails critically
    """
    start_time = time.time()
    datasheet.status = IngestionStatus.PROCESSING

    logger.info(f"Starting ingestion: {datasheet.name}")

    try:
        # Check for duplicates (unless force_update)
        if not force_update and chroma_client.datasheet_exists(datasheet.name):
            logger.info(f"Datasheet already exists, skipping: {datasheet.name}")
            duration = time.time() - start_time

            return IngestionResult(
                datasheet_name=datasheet.name,
                status=IngestionStatus.SKIPPED,
                duration_seconds=duration,
                skipped_reason="Datasheet already exists in ChromaDB (use --force-update to overwrite)",
            )

        # If force_update, delete existing chunks
        if force_update and chroma_client.datasheet_exists(datasheet.name):
            logger.info(f"Force update: deleting existing chunks for {datasheet.name}")
            deleted_count = chroma_client.delete_datasheet(datasheet.name)
            logger.info(f"Deleted {deleted_count} existing chunks")

        # Step 1: Parse markdown
        logger.debug(f"Parsing markdown: {datasheet.markdown_file_path}")
        content = parse_markdown_file(datasheet.markdown_file_path)

        # Step 2: Resolve image paths
        logger.debug(f"Resolving image paths for: {datasheet.name}")
        content, resolved_images = resolve_all_image_paths(
            content,
            datasheet.markdown_file_path,
            datasheet.folder_path,
        )

        # Step 3: Chunk content
        logger.debug(f"Chunking content for: {datasheet.name}")
        chunker = create_chunker()
        text_chunks = chunker.chunk_markdown(content)

        # Step 4: Create ContentChunk instances
        logger.debug(f"Creating {len(text_chunks)} ContentChunk instances")
        chunks = []
        for idx, text in enumerate(text_chunks):
            chunk = ContentChunk(
                text=text,
                datasheet_name=datasheet.name,
                folder_path=str(datasheet.folder_path),
                chunk_index=idx,
                ingestion_timestamp=datasheet.ingestion_timestamp.isoformat() + "Z",
                image_paths=[str(p) for p in resolved_images],
            )
            chunks.append(chunk)

        # Step 5: Insert into ChromaDB (embeddings auto-generated)
        logger.debug(f"Inserting {len(chunks)} chunks into ChromaDB")
        inserted_count = chroma_client.insert_chunks(chunks)

        # Calculate duration
        duration = time.time() - start_time

        # Update datasheet status
        datasheet.status = IngestionStatus.SUCCESS
        datasheet.chunk_count = inserted_count
        datasheet.duration_seconds = duration

        # Log performance
        if duration > PERFORMANCE_TARGET_SECONDS:
            logger.warning(
                f"⚠️  Ingestion exceeded {PERFORMANCE_TARGET_SECONDS}s target: "
                f"{datasheet.name} took {duration:.2f}s"
            )
        else:
            logger.info(
                f"✅ Ingestion complete: {datasheet.name} "
                f"({inserted_count} chunks, {duration:.2f}s)"
            )

        return IngestionResult(
            datasheet_name=datasheet.name,
            status=IngestionStatus.SUCCESS,
            duration_seconds=duration,
            chunks_created=inserted_count,
        )

    except Exception as e:
        duration = time.time() - start_time
        datasheet.status = IngestionStatus.ERROR
        datasheet.error_message = str(e)
        datasheet.duration_seconds = duration

        logger.error(
            f"❌ Ingestion failed: {datasheet.name} - {e}",
            exc_info=True,
        )

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
) -> BatchIngestionReport:
    """
    Ingest batch of datasheets with error handling and progress logging.

    Processes each datasheet independently - one failure doesn't stop the batch.

    Args:
        datasheets: List of datasheets to ingest
        chroma_client: ChromaDB client for storage
        force_update: If True, delete existing chunks before re-ingestion

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
            result = ingest_datasheet(datasheet, chroma_client, force_update)
            results.append(result)

            # Log progress
            if result.is_success():
                logger.info(
                    f"  ✅ Success: {result.chunks_created} chunks, "
                    f"{result.duration_seconds:.2f}s"
                )
            elif result.is_skipped():
                logger.info(f"  ⏭️  Skipped: {result.skipped_reason}")
            elif result.is_error():
                logger.error(f"  ❌ Failed: {result.error_message}")

        except Exception as e:
            # Catch unexpected exceptions at batch level
            logger.error(
                f"  ❌ Unexpected error processing {datasheet.name}: {e}",
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
    logger.info(f"  ✅ Successful: {report.successful}")
    logger.info(f"  ⏭️  Skipped: {report.skipped}")
    logger.info(f"  ❌ Failed: {report.failed}")
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
            f"⚠️  Performance target exceeded: "
            f"{duration:.2f}s > {PERFORMANCE_TARGET_SECONDS}s target "
            f"for {result.datasheet_name}"
        )
