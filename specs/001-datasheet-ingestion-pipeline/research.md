# Research Report: Datasheet Ingestion Pipeline

**Feature**: 001-datasheet-ingestion-pipeline  
**Date**: 2025-01-22  
**Status**: Phase 0 Complete

## Overview

This document consolidates research findings for implementing a LangChain-based datasheet ingestion pipeline targeting Windows with CPU-only processing. All technical unknowns from the planning phase have been resolved.

---

## 1. Semantic Chunking Strategy for Markdown Documents

### Decision
Use a **two-stage chunking approach** with LangChain's experimental markdown splitter followed by recursive character splitting:

1. **Stage 1**: `ExperimentalMarkdownSyntaxTextSplitter` with `strip_headers=False`
   - Preserves markdown structure (headers, tables, code blocks)
   - Groups content by markdown syntax boundaries
   - Keeps tables and code blocks intact as atomic units

2. **Stage 2**: `RecursiveCharacterTextSplitter` applied to each markdown group
   - Target chunk size: 1500 characters
   - Overlap: 15% (~225 characters)
   - Separators prioritized: `\n\n`, `\n`, `. `, ` `, ``

### Rationale
- **Tables integrity**: ExperimentalMarkdownSyntaxTextSplitter recognizes markdown table syntax and prevents mid-table splits
- **Context preservation**: 15% overlap ensures cross-reference context is maintained between chunks
- **Embedding compatibility**: 1500 character limit prevents truncation with most embedding models (typical limit: ~512 tokens ≈ 2048 characters)
- **Section awareness**: Preserving headers in chunks (strip_headers=False) maintains hierarchical context

### Alternatives Considered
- **MarkdownHeaderTextSplitter alone**: Rejected because it splits strictly on headers, breaking tables that span sections
- **RecursiveCharacterTextSplitter only**: Rejected because it lacks markdown syntax awareness, splitting tables and code blocks arbitrarily
- **Fixed-size chunks (512 tokens)**: Rejected because electrical engineering tables and schematics lose meaning when fragmented

### Implementation Notes
```python
from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    RecursiveCharacterTextSplitter
)

# Stage 1: Markdown structure preservation
markdown_splitter = ExperimentalMarkdownSyntaxTextSplitter(strip_headers=False)
markdown_groups = markdown_splitter.split_text(datasheet_content)

# Stage 2: Intelligent character-level splitting within groups
char_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=225,  # 15% of 1500
    separators=["\n\n", "\n", ". ", " ", ""]
)

final_chunks = []
for group in markdown_groups:
    final_chunks.extend(char_splitter.split_text(group))
```

---

## 2. ChromaDB Embedding Function for CPU-Only Environments

### Decision
Use **ChromaDB's default embedding function** (`chromadb.utils.embedding_functions.DefaultEmbeddingFunction()`), which uses `sentence-transformers/all-MiniLM-L6-v2` model.

### Rationale
- **CPU-optimized**: `all-MiniLM-L6-v2` is lightweight (80MB model) and runs efficiently on CPU
- **Windows compatible**: PyTorch CPU-only wheels available for Python 3.13
- **No external APIs**: Runs fully local, satisfying constitution's no-external-calls constraint
- **Good quality**: 384-dimensional embeddings with strong performance for semantic search
- **LangChain integration**: Compatible with `langchain-chroma` library
- **Persistence**: Model downloaded once to cache, reused across runs

### Alternatives Considered
- **OpenAI embeddings**: Rejected due to external API requirement and cost
- **Cohere embeddings**: Rejected due to external API requirement
- **HuggingFace Instructor models**: Rejected due to larger model size (>300MB) and slower CPU inference
- **Custom TF-IDF**: Rejected due to poor semantic understanding compared to transformers

### Implementation Notes
```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path=r"D:\.cache\chromadb",
    settings=Settings(anonymized_telemetry=False)
)

# Default embedding function (sentence-transformers/all-MiniLM-L6-v2)
collection = client.get_or_create_collection(
    name="datasheets",
    metadata={"hnsw:space": "cosine"}  # Cosine similarity for embeddings
)
```

### Performance Expectations
- Embedding speed: ~50-100 chunks/second on modern CPU (Intel i5/i7, AMD Ryzen)
- First run: 2-3 second delay for model download
- Memory usage: ~500MB RAM for model + embeddings

---

## 3. Windows Path Handling Best Practices

### Decision
Use **pathlib.Path** exclusively for all path operations with explicit absolute path conversion.

### Rationale
- **Cross-platform**: pathlib handles Windows backslashes and Unix forward slashes transparently
- **Type safety**: Path objects prevent string concatenation errors
- **Explicit conversions**: `.resolve()` method converts relative to absolute paths reliably
- **Windows long path support**: pathlib automatically handles paths >260 characters with proper Windows 10+ configuration

### Alternatives Considered
- **os.path module**: Rejected because it's less readable and requires manual separator handling
- **String concatenation with os.sep**: Rejected due to error-prone nature and poor type checking
- **Forward slashes only**: Rejected because ChromaDB on Windows stores paths with backslashes internally

### Implementation Notes
```python
from pathlib import Path

# Convert relative image path to absolute
def resolve_image_path(markdown_file_path: Path, relative_image_path: str) -> str:
    """Convert relative image path to absolute Windows path."""
    markdown_dir = markdown_file_path.parent
    image_path = (markdown_dir / relative_image_path).resolve()
    
    # Ensure path exists and is a file
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    return str(image_path)  # ChromaDB metadata stores as string

# Example usage
datasheet_folder = Path(r"D:\datasheets\TL072")
markdown_file = datasheet_folder / "TL072.md"
absolute_image = resolve_image_path(markdown_file, "./images/pinout.png")
# Result: "D:\datasheets\TL072\images\pinout.png"
```

### Edge Cases Handled
- UNC paths: `\\server\share\datasheets`
- Long paths: Paths >260 characters (requires Windows 10+ with long path support enabled)
- Special characters: Spaces, parentheses, Unicode characters in folder names

---

## 4. Duplicate Detection Strategy for ChromaDB

### Decision
Use **metadata filtering on folder name** to check for existing datasheets before ingestion.

### Rationale
- **Unique identifier**: Folder name serves as datasheet identifier (per spec clarification)
- **Efficient query**: ChromaDB's `where` filter on metadata is O(log n) with indexing
- **No false positives**: Exact string match prevents collisions
- **Update support**: Enables clean deletion of all chunks from a datasheet for force-update

### Alternatives Considered
- **Content hashing**: Rejected because it requires reading all chunks to detect duplicates (slow)
- **Document ID prefix**: Rejected because ChromaDB auto-generates UUIDs, requiring custom ID management
- **Separate tracking table**: Rejected because it violates "single source of truth" principle

### Implementation Notes
```python
def datasheet_exists(collection, folder_name: str) -> bool:
    """Check if datasheet already exists in collection."""
    results = collection.get(
        where={"datasheet_name": folder_name},
        limit=1  # Only need to know if any exist
    )
    return len(results['ids']) > 0

def delete_datasheet(collection, folder_name: str) -> int:
    """Delete all chunks for a datasheet. Returns count of deleted chunks."""
    results = collection.get(
        where={"datasheet_name": folder_name}
    )
    chunk_ids = results['ids']
    
    if chunk_ids:
        collection.delete(ids=chunk_ids)
    
    return len(chunk_ids)
```

### Metadata Schema for Duplicate Detection
```python
chunk_metadata = {
    "datasheet_name": "TL072",  # Folder name (unique identifier)
    "folder_path": r"D:\datasheets\TL072",  # Full path for audit
    "chunk_index": 0,  # Sequential chunk number
    "section_heading": "Electrical Characteristics",  # Section context
    "has_table": True,  # Flag for table-containing chunks
    "image_paths": ["D:\\datasheets\\TL072\\images\\pinout.png"],  # List of absolute paths
    "ingestion_timestamp": "2025-01-22T10:30:00Z"  # ISO 8601 format
}
```

---

## 5. CLI Argument Parsing and Error Handling

### Decision
Use **argparse** with structured error messages and exit codes.

### Rationale
- **Standard library**: No additional dependencies
- **Validation**: Built-in type checking and required argument enforcement
- **Help generation**: Automatic `--help` documentation
- **Windows compatible**: Works seamlessly on Windows Python installations

### Alternatives Considered
- **Click**: Rejected to minimize dependencies (argparse is stdlib)
- **Typer**: Rejected to minimize dependencies and avoid FastAPI ecosystem
- **sys.argv parsing**: Rejected due to lack of validation and help text

### Implementation Notes
```python
import argparse
import sys
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest electrical component datasheets into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.ingest D:\\datasheets
  python -m src.cli.ingest D:\\datasheets --force-update
        """
    )
    
    parser.add_argument(
        "datasheets_folder_path",
        type=Path,
        help="Path to folder containing datasheet subfolders"
    )
    
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Re-ingest datasheets that already exist in ChromaDB"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Validation
    if not args.datasheets_folder_path.exists():
        parser.error(f"Folder does not exist: {args.datasheets_folder_path}")
    
    if not args.datasheets_folder_path.is_dir():
        parser.error(f"Path is not a directory: {args.datasheets_folder_path}")
    
    return args

# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_CHROMADB_ERROR = 2
EXIT_INGESTION_ERROR = 3
```

### Error Message Format
```
ERROR [TL072]: Failed to parse markdown file
  File: D:\datasheets\TL072\TL072.md
  Reason: Malformed table at line 45
  Action: Check markdown syntax or skip this datasheet

WARNING [LM358]: Image not found
  Expected: D:\datasheets\LM358\images\pinout.png
  Referenced in: D:\datasheets\LM358\LM358.md:23
  Action: Continuing ingestion without image metadata
```

---

## 6. Additional Python Libraries Required

### Decision
Add the following to `requirements.txt`:

```
# Core dependencies (already present)
chromadb>=0.4.22
langchain>=0.1.0
langchain-chroma>=0.1.0
langchain-community>=0.0.20
langchain_text_splitters>=0.0.1
pathlib  # Python 3.13 has this in stdlib, but explicit for clarity

# Additional required libraries
sentence-transformers>=2.3.1  # For ChromaDB default embeddings (CPU-optimized)
torch>=2.1.0  # PyTorch CPU-only (required by sentence-transformers)
pytest>=7.4.3  # Testing framework
pytest-cov>=4.1.0  # Test coverage reporting
markdown>=3.5.1  # Markdown parsing utilities
```

### Rationale
- **sentence-transformers**: Required for ChromaDB's default embedding function to work
- **torch (CPU-only)**: Backend for sentence-transformers, CPU builds avoid CUDA dependencies
- **pytest ecosystem**: Standard Python testing tools
- **markdown**: Helper library for markdown parsing and validation

### Installation Command (Windows)
```bash
uv sync
```

---

## 7. Logging Strategy

### Decision
Use **Python's logging module** with structured JSON logs for production and human-readable logs for CLI output.

### Rationale
- **Standard library**: No additional dependencies
- **Dual output**: Console (human-readable) + file (JSON for parsing)
- **Log levels**: INFO for progress, WARNING for recoverable issues, ERROR for failures
- **Context**: Include datasheet name, file paths, and timing in all log entries

### Implementation Notes
```python
import logging
import json
import time
from pathlib import Path

def setup_logging(log_level: str):
    """Configure logging with console and file handlers."""
    logger = logging.getLogger("datasheet_ingestion")
    logger.setLevel(log_level)
    
    # Console handler (human-readable)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s [%(datasheet)s]: %(message)s")
    )
    
    # File handler (JSON structured logs)
    log_dir = Path(".logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / f"ingestion_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    file_handler.setFormatter(JsonFormatter())
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": record.levelname,
            "datasheet": getattr(record, "datasheet", "UNKNOWN"),
            "message": record.getMessage(),
            "duration_ms": getattr(record, "duration_ms", None),
            "chunk_count": getattr(record, "chunk_count", None)
        }
        return json.dumps(log_data)
```

---

## 8. Performance Optimization Strategies

### Decision
Implement **single-threaded sequential processing** with timing instrumentation and warning thresholds.

### Rationale
- **Simplicity**: Easier to debug and maintain than parallel processing
- **ChromaDB constraints**: ChromaDB Python client is not thread-safe for writes
- **CPU bottleneck**: Embedding generation is CPU-bound; multi-threading adds overhead without benefit
- **Memory management**: Sequential processing limits peak memory usage
- **Sufficient performance**: Targets (<30 sec per datasheet, <30 min for 100 datasheets) achievable without parallelization

### Alternatives Considered
- **Multiprocessing**: Rejected due to ChromaDB client serialization issues and added complexity
- **Asyncio**: Rejected because embedding generation and ChromaDB operations are not I/O-bound
- **Batch embedding**: Considered but deferred to future optimization (sentence-transformers supports batching)

### Implementation Notes
```python
import time

def ingest_datasheet(datasheet_folder: Path) -> dict:
    """Ingest single datasheet with timing."""
    start_time = time.time()
    
    try:
        # Parsing, chunking, embedding, storage...
        result = {
            "status": "success",
            "chunks_created": 42,
            "duration_seconds": time.time() - start_time
        }
        
        # Warning if exceeds performance target
        if result["duration_seconds"] > 30:
            logger.warning(
                f"Datasheet ingestion exceeded 30-second target",
                extra={
                    "datasheet": datasheet_folder.name,
                    "duration_seconds": result["duration_seconds"]
                }
            )
        
        return result
    
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "duration_seconds": time.time() - start_time
        }
```

---

## 9. Testing Strategy

### Decision
Implement **three-tier testing**:
1. **Unit tests**: Test chunking, parsing, validation logic in isolation
2. **Integration tests**: Test ChromaDB operations with temporary test collections
3. **Fixture-based tests**: Use sample datasheets with known structure for end-to-end validation

### Rationale
- **Fast feedback**: Unit tests run in <1 second without ChromaDB
- **Isolation**: Integration tests use separate test collections, not production data
- **Reproducibility**: Fixtures ensure consistent test behavior across environments
- **Coverage targets**: >80% code coverage for core ingestion logic

### Implementation Notes
```python
# tests/unit/test_chunker.py
import pytest
from src.ingestion.chunker import semantic_chunk

def test_table_preservation():
    """Tables should remain intact within single chunk."""
    markdown_with_table = """
# Section 1
Some text.

| Pin | Function | Voltage |
|-----|----------|---------|
| 1   | VCC      | 5V      |
| 2   | GND      | 0V      |

More text.
"""
    chunks = semantic_chunk(markdown_with_table)
    
    # Table should be in single chunk
    table_chunks = [c for c in chunks if "| Pin |" in c]
    assert len(table_chunks) == 1
    assert "| 1   | VCC" in table_chunks[0]
    assert "| 2   | GND" in table_chunks[0]

# tests/integration/test_chroma_client.py
import pytest
import chromadb
from src.ingestion.chroma_client import ChromaClient

@pytest.fixture
def test_collection():
    """Create temporary ChromaDB collection for testing."""
    client = chromadb.Client()  # In-memory client
    collection = client.create_collection("test_datasheets")
    yield collection
    client.delete_collection("test_datasheets")

def test_duplicate_detection(test_collection):
    """Should detect existing datasheets correctly."""
    chroma_client = ChromaClient(test_collection)
    
    # First ingestion
    assert not chroma_client.datasheet_exists("TL072")
    chroma_client.ingest_chunks("TL072", ["chunk1"], [{"idx": 0}])
    
    # Second check
    assert chroma_client.datasheet_exists("TL072")
```

---

## 10. Risk Analysis and Mitigation

### Risk 1: Large Tables Exceed Chunk Size Limit
**Probability**: Medium | **Impact**: High  
**Mitigation**: 
- Log warning when a single markdown group (table) exceeds 1500 characters
- Store large tables as single chunks even if >1500 chars (accept truncation risk)
- Future: Implement table splitting logic that preserves headers

### Risk 2: Windows Path Encoding Issues with Special Characters
**Probability**: Low | **Impact**: Medium  
**Mitigation**: 
- Use pathlib exclusively (handles encoding automatically)
- Test with sample datasheets containing spaces, parentheses, Unicode
- Document known limitations (avoid `< > : " | ? *` in folder names)

### Risk 3: ChromaDB Collection Size Limits
**Probability**: Low | **Impact**: High  
**Mitigation**: 
- Monitor collection size during ingestion (log warnings at 50k, 100k chunks)
- Document scaling limits (ChromaDB handles millions of embeddings)
- Future: Implement collection sharding by component type

### Risk 4: CPU Embedding Performance Slower Than Expected
**Probability**: Medium | **Impact**: Medium  
**Mitigation**: 
- Performance targets are warnings, not hard failures
- Log detailed timing per datasheet for bottleneck analysis
- Future: Implement batch embedding (process 10 chunks at once)

### Risk 5: Markdown Parser Fails on Complex Tables
**Probability**: Medium | **Impact**: Medium  
**Mitigation**: 
- Use best-effort parsing with error recovery
- Log malformed tables for manual review
- Continue ingestion with partial content rather than failing entire datasheet

---

## Summary

All technical unknowns have been resolved with specific implementation decisions:

1. ✅ **Chunking strategy**: Two-stage approach with ExperimentalMarkdownSyntaxTextSplitter + RecursiveCharacterTextSplitter
2. ✅ **Embedding model**: ChromaDB default (sentence-transformers/all-MiniLM-L6-v2) for CPU efficiency
3. ✅ **Path handling**: pathlib.Path for Windows compatibility
4. ✅ **Duplicate detection**: Metadata filtering on folder name
5. ✅ **CLI framework**: argparse with structured error handling
6. ✅ **Dependencies**: Added sentence-transformers, torch (CPU), pytest, markdown
7. ✅ **Logging**: Dual output (console + JSON file) with structured context
8. ✅ **Performance**: Sequential processing with timing instrumentation
9. ✅ **Testing**: Three-tier strategy with fixtures
10. ✅ **Risks**: Identified and mitigated with logging and graceful degradation

**Phase 0 Status**: ✅ Complete - Ready to proceed to Phase 1 (Design & Contracts)
