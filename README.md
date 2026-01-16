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
✅ **Performance Evaluation** - RAGAS-based evaluation for optimizing chunk sizes

## Requirements

- **Python**: 3.13+
- **Platform**: Windows (primary), cross-platform compatible
- **Dependencies**: Managed with `uv` package manager

## Installation

### 1. Clone the Repository

### 2. Install uv (if not already installed)

### 3. Install Dependencies

```bash
uv sync
```

## Quick Start

### Basic Usage

Ingest all datasheets from a folder:

```bash
# Using main.py entry point (recommended)
python main.py D:\datasheets\components

# Or with uv
uv run main.py D:\datasheets\components
```

### Force Update

Re-ingest existing datasheets (deletes and re-creates chunks):

```bash
python main.py D:\datasheets\components --force-update
```

### Custom Log Level

Set logging verbosity:

```bash
python main.py D:\datasheets\components --log-level DEBUG
```

### Custom Chunking Parameters

Adjust chunk size and overlap for different document types:

```bash
# Larger chunks for detailed datasheets
python main.py D:\datasheets\components --chunk-size 2048 --chunk-overlap 200

# Smaller chunks for concise datasheets
python main.py D:\datasheets\components --chunk-size 512 --chunk-overlap 50
```

### In-Memory Database (Experimental)

Use ephemeral ChromaDB for experiments without persisting data:

```bash
python main.py D:\datasheets\components --in-mem-chroma
```

## CLI Reference

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `datasheets_folder_path` | Positional | Required | Path to folder containing datasheet subfolders |
| `--force-update` | Flag | False | Delete and re-ingest existing datasheets |
| `--log-level` | Choice | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `--chunk-size` | Integer | 1024 | Target chunk size in tokens |
| `--chunk-overlap` | Integer | Auto (15%) | Chunk overlap in tokens |
| `--in-mem-chroma` | Flag | False | Use in-memory ChromaDB (data not persisted) |

## Folder Structure

Datasheets must follow this structure:

```
datasheets/
├── TL072/
│   ├── TL072.md          # Exactly one .md file per folder
│   ├── pinout.png
│   └── schematic.png
├── LM358/
│   ├── LM358.md
│   └── diagram.png
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

- **Storage**: Persistent at `CHROMADB_PATH` (default: `D:\.cache\chromadb`)
  - Can be overridden with `--in-mem-chroma` for ephemeral storage
- **Collection**: `datasheets` (configurable via `CHROMADB_COLLECTION`)
- **Embedding Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Similarity Metric**: Cosine similarity (HNSW index)
- **Default Chunk Size**: 1024 tokens (configurable via `--chunk-size`)
- **Default Chunk Overlap**: Auto (15% of chunk size, configurable via `--chunk-overlap`)

## Logging

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

## Performance Evaluation

The `evaluation/` folder contains tools for evaluating and optimizing RAG configurations using RAGAS metrics.

### Quick Evaluation

```bash
# Run quick test with 5 Q&A pairs
uv run python evaluation/quick_test.py

# Run full evaluation with all configurations
uv run python evaluation/evaluate_rag.py
```

### Dynamic Configuration

The evaluation system uses `evaluation/experiments.csv` to control all pipeline parameters. Column headers are automatically converted to function arguments (e.g., `chunk-size` → `chunk_size`), allowing complete control without code changes.

**Adding new parameters:**
1. Add CLI argument in `src/cli/ingest.py`
2. Add parameter to `ingest_batch()` in `src/ingestion/pipeline.py`
3. Add column to `evaluation/experiments.csv`
4. No changes needed in `evaluate_rag.py`!

### Metrics Evaluated

- **Faithfulness**: Hallucination avoidance (0.0-1.0)
- **Answer Relevancy**: Answer relevance to question (0.0-1.0)
- **Factual Correctness**: Answer accuracy (0.0-1.0)
- **Context Relevance**: Retrieval quality (0.0-1.0)
- **Summary Score**: Overall response quality (0.0-1.0)

See [`evaluation/README.md`](src/evaluation/README.md) for detailed documentation.

## Exit Codes

- `0`: Success - all datasheets ingested successfully
- `1`: Validation error - invalid folder path or arguments
- `2`: ChromaDB error - database connection/initialization failed
- `3`: Ingestion error - one or more datasheets failed to ingest


## Architecture

### Pipeline Flow

```
Folder Path → Discovery → Duplicate Check → Parse Markdown
    → Resolve Image Paths → Semantic Chunking → Generate Embeddings
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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Acknowledgments

- **LangChain**: Framework for LLM-powered applications
- **ChromaDB**: Vector database for embeddings
- **sentence-transformers**: State-of-the-art sentence embeddings
- **uv**: Fast Python package manager
