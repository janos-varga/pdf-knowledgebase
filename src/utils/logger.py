"""
Structured logging configuration for the datasheet ingestion pipeline.

Provides dual-output logging:
- Console: Human-readable format for CLI users
- File: JSON format for machine parsing and analysis
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Convert log record to JSON format.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                log_data[key] = value

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Format log records for human-readable console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record for console with colors.

        Args:
            record: Log record to format

        Returns:
            Colored, human-readable log string
        """
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # Build log message
        log_parts = [
            f"{color}{record.levelname:8}{reset}",
            f"[{timestamp}]",
            f"{record.getMessage()}",
        ]

        # Add exception info if present
        if record.exc_info:
            log_parts.append(f"\n{self.formatException(record.exc_info)}")

        return " ".join(log_parts)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True,
) -> logging.Logger:
    """
    Configure structured logging with console and file handlers.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to JSON log file (default: .logs/ingestion_{timestamp}.json)
        console_output: Whether to output logs to console

    Returns:
        Configured logger instance
    """
    # Create root logger
    logger = logging.getLogger("datasheet_ingestion")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()  # Remove existing handlers

    # Console handler (human-readable)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)

    # File handler (JSON format)
    if log_file is None:
        log_dir = Path(".logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ingestion_{timestamp}.json"

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    logger.info(f"Logging configured: level={log_level}, file={log_file}")
    return logger


def get_logger(name: str = "datasheet_ingestion") -> logging.Logger:
    """
    Get logger instance for module.

    Args:
        name: Logger name (typically module name)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_structured(
    logger: logging.Logger,
    level: str,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log message with structured metadata.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **kwargs: Additional structured data to include in log
    """
    log_func = getattr(logger, level.lower())
    log_func(message, extra=kwargs)


def format_error_message(
    datasheet_name: str,
    file_path: Optional[Path],
    error_summary: str,
    error_reason: str,
    suggested_action: str,
) -> str:
    """
    Format a structured error message with actionable guidance.

    Args:
        datasheet_name: Name of the datasheet that failed
        file_path: Path to the file that caused the error
        error_summary: Brief summary of the error
        error_reason: Detailed reason for the error
        suggested_action: Suggested action to resolve the error

    Returns:
        Formatted error message string

    Examples:
        >>> format_error_message(
        ...     "TL072",
        ...     Path("D:/datasheets/TL072/TL072.md"),
        ...     "Markdown parsing failed",
        ...     "File is empty or contains no valid content",
        ...     "Add content to the markdown file and try again"
        ... )
        '❌ Datasheet: TL072\\n   File: D:/datasheets/TL072/TL072.md\\n   Error: Markdown parsing failed\\n   Reason: File is empty or contains no valid content\\n   Action: Add content to the markdown file and try again'
    """
    lines = [
        f"❌ Datasheet: {datasheet_name}",
    ]

    if file_path:
        lines.append(f"   File: {file_path}")

    lines.extend([
        f"   Error: {error_summary}",
        f"   Reason: {error_reason}",
        f"   Action: {suggested_action}",
    ])

    return "\n".join(lines)


def log_datasheet_status(
    logger: logging.Logger,
    datasheet_name: str,
    status: str,
    duration_seconds: Optional[float] = None,
    chunks_created: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Log datasheet ingestion status with structured metadata.

    Args:
        logger: Logger instance
        datasheet_name: Name of the datasheet
        status: Ingestion status (success/error/skipped)
        duration_seconds: Time taken for ingestion
        chunks_created: Number of chunks created
        error_message: Error details if failed
    """
    metadata = {
        "datasheet_name": datasheet_name,
        "status": status,
    }

    if duration_seconds is not None:
        metadata["duration_seconds"] = round(duration_seconds, 2)

    if chunks_created is not None:
        metadata["chunks_created"] = chunks_created

    if error_message:
        metadata["error_message"] = error_message

    level = "info" if status == "success" else "warning" if status == "skipped" else "error"
    log_structured(logger, level, f"Datasheet {status}: {datasheet_name}", **metadata)
