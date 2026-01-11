#!/usr/bin/env python3
"""
Main entry point for the PDF Knowledge Base datasheet ingestion pipeline.

This is a convenience wrapper that can be run directly:
    python main.py <datasheets_folder> [--force-update] [--log-level LEVEL]

Or via uv:
    uv run main.py <datasheets_folder>

For more information, see README.md or run:
    python main.py --help
"""

import sys

from src.cli.ingest import main as cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
