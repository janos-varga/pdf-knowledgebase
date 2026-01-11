"""
CLI entry point for datasheet ingestion pipeline.

Provides command-line interface for ingesting datasheets into ChromaDB:
    - Argument parsing
    - Environment variable support
    - Console output formatting
    - Exit codes for automation
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from src.ingestion.chroma_client import ChromaDBClient
from src.ingestion.pipeline import discover_datasheets, ingest_batch
from src.utils.logger import setup_logging
from src.utils.validators import validate_folder_path

logger = logging.getLogger("datasheet_ingestion.cli")


# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_CHROMADB_ERROR = 2
EXIT_INGESTION_ERROR = 3


# Environment variables
ENV_CHROMADB_PATH = "CHROMADB_PATH"
ENV_CHROMADB_COLLECTION = "CHROMADB_COLLECTION"

# Defaults
DEFAULT_CHROMADB_PATH = Path(r"D:\.cache\chromadb")
DEFAULT_COLLECTION_NAME = "datasheets"
DEFAULT_LOG_LEVEL = "INFO"


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="datasheet-ingest",
        description="Ingest electrical component datasheets into ChromaDB for AI-assisted queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest multiple datasheets from a folder containing subfolders
  python main.py D:\\datasheets\\components
  uv run main.py D:\\datasheets\\components

  # Ingest a single datasheet from its folder
  python main.py D:\\datasheets\\components\\TL072

  # Using module directly
  python -m src.cli.ingest D:\\datasheets\\components

  # Force update existing datasheets
  python main.py D:\\datasheets\\components --force-update

  # Set custom log level
  python main.py D:\\datasheets\\components --log-level DEBUG

Environment Variables:
  CHROMADB_PATH          Path to ChromaDB storage (default: D:\\.cache\\chromadb)
  CHROMADB_COLLECTION    Collection name (default: datasheets)

Exit Codes:
  0  Success - all datasheets ingested successfully
  1  Validation error - invalid folder path or arguments
  2  ChromaDB error - database connection or initialization failed
  3  Ingestion error - one or more datasheets failed to ingest
        """,
    )

    # Required positional argument
    parser.add_argument(
        "datasheets_folder_path",
        type=str,
        help="Path to folder containing datasheet subfolders or a single datasheet folder",
    )

    # Optional flags
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Force update existing datasheets (delete and re-ingest)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=DEFAULT_LOG_LEVEL,
        help=f"Logging level (default: {DEFAULT_LOG_LEVEL})",
    )

    return parser.parse_args()


def get_chromadb_config() -> tuple[Path, str]:
    """
    Get ChromaDB configuration from environment variables or defaults.

    Returns:
        Tuple of (chromadb_path, collection_name)
    """
    chromadb_path_str = os.environ.get(ENV_CHROMADB_PATH)
    if chromadb_path_str:
        chromadb_path = Path(chromadb_path_str)
        logger.info(f"Using ChromaDB path from environment: {chromadb_path}")
    else:
        chromadb_path = DEFAULT_CHROMADB_PATH
        logger.info(f"Using default ChromaDB path: {chromadb_path}")

    collection_name = os.environ.get(ENV_CHROMADB_COLLECTION, DEFAULT_COLLECTION_NAME)
    if ENV_CHROMADB_COLLECTION in os.environ:
        logger.info(f"Using collection name from environment: {collection_name}")
    else:
        logger.info(f"Using default collection name: {collection_name}")

    return chromadb_path, collection_name


def print_banner(
    args: argparse.Namespace, chromadb_path: Path, collection_name: str
) -> None:
    """
    Print CLI banner with configuration summary.

    Args:
        args: Parsed command-line arguments
        chromadb_path: Path to ChromaDB storage
        collection_name: Collection name
    """
    banner = f"""
{"=" * 70}
  Datasheet Ingestion Pipeline
{"=" * 70}
  Datasheets Folder:  {args.datasheets_folder_path}
  ChromaDB Path:      {chromadb_path}
  Collection:         {collection_name}
  Force Update:       {"Yes" if args.force_update else "No"}
  Log Level:          {args.log_level}
{"=" * 70}
"""
    print(banner)


def print_progress(current: int, total: int, datasheet_name: str, status: str) -> None:
    """
    Print per-datasheet progress.

    Args:
        current: Current datasheet number (1-indexed)
        total: Total number of datasheets
        datasheet_name: Name of datasheet being processed
        status: Status message (e.g., "Processing...", "Success", "Failed")
    """
    logger.info(f"[{current}/{total}] {datasheet_name}: {status}")


def print_summary(report) -> None:
    """
    Print batch ingestion summary report.

    Args:
        report: BatchIngestionReport instance
    """
    # Print summary from report
    summary = report.summary()
    logger.info("" + summary)


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0=success, 1=validation error, 2=ChromaDB error, 3=ingestion error)
    """
    # Parse arguments
    args = parse_arguments()

    # Setup logging
    setup_logging(log_level=args.log_level)
    logger.info("Datasheet ingestion CLI started")

    try:
        # Get ChromaDB configuration
        chromadb_path, collection_name = get_chromadb_config()

        # Print banner
        print_banner(args, chromadb_path, collection_name)

        # Validate folder path
        folder_path = Path(args.datasheets_folder_path)
        try:
            validate_folder_path(folder_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Validation error: {e}")
            logger.error(f"[X] Error: {e}")
            logger.error(
                "Please provide a valid folder path containing datasheet subfolders."
            )
            return EXIT_VALIDATION_ERROR

        # Discover datasheets
        logger.info("Discovering datasheets...")
        try:
            datasheets = discover_datasheets(folder_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Discovery error: {e}")
            logger.error(f"[X] Error: {e}")
            return EXIT_VALIDATION_ERROR

        if not datasheets:
            logger.warning("[!] No datasheets found in folder.")
            logger.warning("   Each datasheet should be in its own subfolder with one .md file.")
            return EXIT_VALIDATION_ERROR

        logger.info(f"Found {len(datasheets)} datasheets")

        # Initialize ChromaDB client
        logger.info("Initializing ChromaDB...")
        try:
            chroma_client = ChromaDBClient(
                chromadb_path=chromadb_path,
                collection_name=collection_name,
            )
        except RuntimeError as e:
            logger.error(f"ChromaDB initialization error: {e}")
            logger.error(f"[X] ChromaDB Error: {e}")
            logger.error("Possible causes:")
            logger.error("  - ChromaDB path is not accessible")
            logger.error("  - Insufficient disk space")
            logger.error("  - Permission denied")
            return EXIT_CHROMADB_ERROR

        # Validate ChromaDB connection
        is_valid, error_msg = chroma_client.validate_connection()
        if not is_valid:
            logger.error(f"ChromaDB validation error: {error_msg}")
            logger.error(f"[X] ChromaDB Validation Error: {error_msg}")
            return EXIT_CHROMADB_ERROR

        logger.info("ChromaDB initialized successfully")

        # Run batch ingestion
        logger.info("Starting batch ingestion...")
        try:
            report = ingest_batch(
                datasheets,
                chroma_client,
                force_update=args.force_update,
            )
        except RuntimeError as e:
            logger.error(f"Batch ingestion error: {e}")
            logger.error(f"[X] Batch Ingestion Error: {e}")
            return EXIT_INGESTION_ERROR

        # Print summary
        print_summary(report)

        # Determine exit code
        if report.failed > 0:
            logger.warning(f"Batch completed with {report.failed} failures")
            return EXIT_INGESTION_ERROR
        elif report.successful > 0:
            logger.info("Batch completed successfully")
            return EXIT_SUCCESS
        else:
            logger.warning("Batch completed with no successful ingestions")
            return EXIT_INGESTION_ERROR

    except KeyboardInterrupt:
        logger.warning("[!] Interrupted by user")
        logger.warning("CLI interrupted by user")
        return EXIT_INGESTION_ERROR

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        logger.error(f"[X] Unexpected Error: {e}")
        return EXIT_INGESTION_ERROR


if __name__ == "__main__":
    sys.exit(main())
