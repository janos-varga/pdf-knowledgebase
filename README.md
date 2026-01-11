# Datasheet Ingestion Pipeline

A LangChain-based CLI tool for ingesting electrical component datasheets into ChromaDB for AI-assisted queries via Chroma MCP Server.

## Overview

This pipeline enables engineers to build a searchable knowledge base of component datasheets by:
- Parsing markdown files with tables and images
- Performing semantic chunking that respects document structure
- Converting relative image paths to absolute paths
- Storing chunks with rich metadata in ChromaDB

## Features

✅ **Smart Ingestion** - Two-stage semantic chunking preserves tables and code blocks  
✅ **Incremental Updates** - Duplicate detection with force-update capability  
✅ **Error Handling** - Graceful error recovery with actionable feedback  
✅ **Performance Tracking** - Logs timing and warns when targets are exceeded  
✅ **Structured Logging** - Human-readable console + JSON file output  

## Requirements

- **Python**: 3.10 or higher
- **Platform**: Windows (primary), cross-platform compatible
- **Dependencies**: Managed with `uv` package manager

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pdf-knowledgebase
```

### 2. Install uv (if not already installed)

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Install Dependencies

```bash
# Install PyTorch CPU-only first (required for embeddings)
uv pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install project dependencies
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

Ingest all datasheets from a folder:

```bash
uv run python -m src.cli.ingest D:\datasheets\components
```

### Force Update

Re-ingest existing datasheets (deletes and re-creates chunks):

```bash
uv run python -m src.cli.ingest D:\datasheets\components --force-update
```

### Custom Log Level

Set logging verbosity:

```bash
uv run python -m src.cli.ingest D:\datasheets\components --log-level DEBUG
```

## Folder Structure

Datasheets must follow this structure:

```
datasheets/
├── TL072/
│   ├── TL072.md          # Exactly one .md file per folder
│   └── images/
│       ├── pinout.png
│       └── schematic.png
├── LM358/
│   ├── LM358.md
│   └── images/
│       └── diagram.png
└── ...
```

**Requirements:**
- Each datasheet in its own subfolder
- Exactly one `.md` file per datasheet folder
- Images are optional (referenced in markdown)
- Folder names should avoid Windows reserved characters

## Configuration

### Environment Variables

```bash
# ChromaDB storage path (default: D:\.cache\chromadb)
CHROMADB_PATH=D:\my-custom-path\chromadb

# Collection name (default: datasheets)
CHROMADB_COLLECTION=my_datasheets
```

### ChromaDB Settings

- **Storage**: Persistent at `D:\.cache\chromadb` (configurable)
- **Collection**: `datasheets` (configurable)
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Similarity Metric**: Cosine similarity
- **Chunk Size**: 1500 characters target, 2000 max

## Performance

### Targets

- **Single datasheet**: < 30 seconds (20-page document)
- **Batch (100 datasheets)**: < 30 minutes (avg 15 pages each)
- **Success rate**: ≥ 95% for well-formed datasheets

### Optimization Tips

1. **CPU-only mode**: Uses CPU-optimized embedding model (no GPU required)
2. **Parallel processing**: Tasks marked `[P]` can run concurrently
3. **Incremental updates**: Use `--force-update` only when needed

## Output

### Console Output

```
======================================================================
  Datasheet Ingestion Pipeline
======================================================================
  Datasheets Folder:  D:\datasheets\components
  ChromaDB Path:      D:\.cache\chromadb
  Collection:         datasheets
  Force Update:       No
  Log Level:          INFO
======================================================================

Discovering datasheets...
Found 2 datasheets

Initializing ChromaDB...
ChromaDB initialized successfully

Starting batch ingestion...

[1/2] TL072: Processing...
  ✅ Success: 9 chunks, 1.56s
[2/2] LM358: Processing...
  ✅ Success: 12 chunks, 1.96s

============================================================
Ingestion Batch Summary
============================================================
Total Datasheets: 2
  ✅ Successful: 2
  ⏭️  Skipped: 0
  ❌ Failed: 0

Total Chunks Created: 21
Total Duration: 3.52 seconds
Success Rate: 100.0%
============================================================
```

### Log Files

Structured JSON logs are saved to `.logs/ingestion_{timestamp}.json`:

```json
{
  "timestamp": "2025-01-22T10:30:00Z",
  "level": "INFO",
  "logger": "datasheet_ingestion.pipeline",
  "message": "Ingestion complete: TL072 (9 chunks, 1.56s)",
  "datasheet_name": "TL072",
  "status": "success",
  "duration_seconds": 1.56,
  "chunks_created": 9
}
```

## Error Handling

### Common Issues

#### No datasheets found
```
⚠️  No datasheets found in folder.
   Each datasheet should be in its own subfolder with one .md file.
```
**Solution**: Check folder structure matches requirements

#### Multiple markdown files
```
❌ Datasheet: TL072
   Error: Multiple .md files found in folder
   Reason: Found TL072.md, TL072_backup.md
   Action: Keep only one .md file per datasheet folder
```
**Solution**: Remove extra markdown files

#### Empty markdown file
```
❌ Datasheet: LM358
   Error: Markdown parsing failed
   Reason: File is empty or contains no valid content
   Action: Add content to the markdown file and try again
```
**Solution**: Add content to the markdown file

#### Missing image (warning only)
```
⚠️  Could not resolve image path 'images/missing.png' - keeping original reference
```
**Solution**: Add missing image or update markdown reference

## Exit Codes

- `0`: Success - all datasheets ingested successfully
- `1`: Validation error - invalid folder path or arguments
- `2`: ChromaDB error - database connection/initialization failed
- `3`: Ingestion error - one or more datasheets failed to ingest

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_chunker.py
```

### Code Quality

```bash
# Lint with Ruff
uv run ruff check src/

# Format with Ruff
uv run ruff format src/
```

## Architecture

### Pipeline Flow

```
Folder Path → Discovery → Duplicate Check → Parse Markdown
    → Resolve Images → Semantic Chunking → Generate Embeddings
    → Store in ChromaDB → Report Results
```

### Key Components

- **markdown_parser.py**: UTF-8 parsing, image path resolution
- **chunker.py**: Two-stage semantic chunking with table preservation
- **chroma_client.py**: ChromaDB operations (insert, delete, duplicate check)
- **pipeline.py**: Orchestration, error handling, performance tracking
- **ingest.py**: CLI interface, argument parsing, console output

## Metadata Schema

Each chunk includes:

- `datasheet_name`: Folder name (unique identifier)
- `folder_path`: Absolute path to datasheet folder
- `chunk_index`: Sequential position (0, 1, 2, ...)
- `section_heading`: Markdown section heading (if available)
- `has_table`: Boolean flag for table presence
- `has_code_block`: Boolean flag for code block presence
- `image_paths`: List of absolute paths to referenced images
- `ingestion_timestamp`: ISO 8601 timestamp

## Integration with Chroma MCP Server

Once datasheets are ingested, query them using Chroma MCP Server:

```python
# Semantic search
results = collection.query(
    query_texts=["op-amp input impedance specifications"],
    n_results=5,
    where={"has_table": True}
)

# Get all chunks for specific datasheet
results = collection.get(
    where={"datasheet_name": "TL072"}
)
```

## Troubleshooting

### ChromaDB Path Not Found

**Issue**: `ChromaDB path does not exist: D:\.cache\chromadb`

**Solution**: The path will be created automatically. Check permissions on parent directory.

### Permission Denied

**Issue**: `Permission denied: cannot write to D:\.cache\chromadb`

**Solution**: Run as administrator or use a different path via `CHROMADB_PATH` environment variable.

### PyTorch Installation Issues

**Issue**: PyTorch installs GPU version by default (large download)

**Solution**: Install CPU-only version first:
```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Acknowledgments

- **LangChain**: Framework for LLM-powered applications
- **ChromaDB**: Vector database for embeddings
- **sentence-transformers**: State-of-the-art sentence embeddings
- **uv**: Fast Python package manager
