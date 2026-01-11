# Data Model: Datasheet Ingestion Pipeline

**Feature**: 001-datasheet-ingestion-pipeline  
**Date**: 2025-01-22  
**Status**: Phase 1 Design

## Overview

This document defines the domain entities, relationships, validation rules, and state transitions for the datasheet ingestion pipeline. The model supports the document-centric architecture required by the project constitution.

---

## Entity Definitions

### 1. Datasheet

Represents a single electrical component's technical documentation, organized as a folder containing markdown and images.

#### Attributes

| Attribute | Type | Required | Description | Validation |
|-----------|------|----------|-------------|------------|
| `name` | `str` | Yes | Unique identifier derived from folder name | Non-empty, valid folder name |
| `folder_path` | `Path` | Yes | Absolute path to datasheet folder | Must exist, must be directory |
| `markdown_file_path` | `Path` | Yes | Absolute path to markdown file within folder | Must exist, extension `.md` |
| `image_paths` | `list[Path]` | No | List of absolute paths to images in folder | Each path must exist if provided |
| `component_type` | `str` | No | Type of component (e.g., "op-amp", "microcontroller") | Future: derive from content |
| `ingestion_timestamp` | `datetime` | Yes | ISO 8601 timestamp when ingestion started | Auto-generated |
| `status` | `IngestionStatus` | Yes | Current ingestion state | Enum: pending, processing, success, error, skipped |
| `error_message` | `str` | No | Error details if status is "error" | Only present on error |
| `chunk_count` | `int` | No | Number of chunks created (if successful) | ≥ 0 |
| `duration_seconds` | `float` | No | Time taken for ingestion | ≥ 0.0 |

#### Python Model

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional

class IngestionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"

@dataclass
class Datasheet:
    name: str
    folder_path: Path
    markdown_file_path: Path
    ingestion_timestamp: datetime
    status: IngestionStatus
    image_paths: list[Path] = None
    component_type: Optional[str] = None
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
    duration_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Validate datasheet attributes."""
        if not self.name:
            raise ValueError("Datasheet name cannot be empty")
        
        if not self.folder_path.exists():
            raise FileNotFoundError(f"Folder does not exist: {self.folder_path}")
        
        if not self.folder_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.folder_path}")
        
        if not self.markdown_file_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {self.markdown_file_path}")
        
        if self.markdown_file_path.suffix.lower() != '.md':
            raise ValueError(f"File is not markdown: {self.markdown_file_path}")
        
        if self.image_paths is None:
            self.image_paths = []
    
    @classmethod
    def from_folder(cls, folder_path: Path, ingestion_timestamp: datetime = None) -> "Datasheet":
        """
        Create Datasheet from folder path.
        
        Expects folder structure:
        datasheets/
          └── TL072/
              ├── TL072.md
              └── images/
                  ├── pinout.png
                  └── schematic.png
        """
        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.utcnow()
        
        folder_path = folder_path.resolve()
        name = folder_path.name
        
        # Find markdown file (expect exactly one)
        md_files = list(folder_path.glob("*.md"))
        if len(md_files) == 0:
            raise FileNotFoundError(f"No markdown file found in {folder_path}")
        if len(md_files) > 1:
            raise ValueError(f"Multiple markdown files found in {folder_path}: {md_files}")
        
        markdown_file_path = md_files[0]
        
        # Find all images (optional)
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg"}
        image_paths = [
            p for p in folder_path.rglob("*")
            if p.is_file() and p.suffix.lower() in image_extensions
        ]
        
        return cls(
            name=name,
            folder_path=folder_path,
            markdown_file_path=markdown_file_path,
            ingestion_timestamp=ingestion_timestamp,
            status=IngestionStatus.PENDING,
            image_paths=image_paths
        )
```

#### Validation Rules

1. **Folder structure**: Each datasheet folder must contain exactly one `.md` file
2. **Unique identification**: Folder name must be unique within the batch
3. **Path resolution**: All paths stored as absolute paths (no relative paths)
4. **Image validation**: Images are optional; missing images trigger warnings, not errors
5. **Name constraints**: Folder names should avoid Windows-reserved characters (`< > : " | ? * /`)

---

### 2. ContentChunk

Represents a semantically meaningful segment of a datasheet after intelligent chunking.

#### Attributes

| Attribute | Type | Required | Description | Validation |
|-----------|------|----------|-------------|------------|
| `id` | `str` | Yes | Unique identifier (UUID v4) | Auto-generated by ChromaDB |
| `text` | `str` | Yes | Chunk text content | 1 ≤ length ≤ 2000 characters |
| `embedding` | `list[float]` | Yes | Vector embedding (384 dimensions) | Auto-generated by ChromaDB |
| `datasheet_name` | `str` | Yes | Parent datasheet identifier | Must match Datasheet.name |
| `folder_path` | `str` | Yes | Parent datasheet folder path | Stored as string for ChromaDB |
| `chunk_index` | `int` | Yes | Sequential position within datasheet | ≥ 0, unique per datasheet |
| `section_heading` | `str` | No | Markdown section heading (if available) | Extracted from content |
| `has_table` | `bool` | Yes | Flag indicating table presence | Default: False |
| `has_code_block` | `bool` | Yes | Flag indicating code block presence | Default: False |
| `image_paths` | `list[str]` | No | Absolute paths to images referenced in chunk | Empty list if none |
| `ingestion_timestamp` | `str` | Yes | ISO 8601 timestamp | Must match parent datasheet |
| `source_page_hint` | `int` | No | Approximate page number (future) | ≥ 1 if provided |

#### Python Model

```python
from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class ContentChunk:
    text: str
    datasheet_name: str
    folder_path: str
    chunk_index: int
    ingestion_timestamp: str
    has_table: bool = False
    has_code_block: bool = False
    section_heading: Optional[str] = None
    image_paths: list[str] = field(default_factory=list)
    source_page_hint: Optional[int] = None
    
    def __post_init__(self):
        """Validate chunk attributes."""
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Chunk text cannot be empty")
        
        if len(self.text) > 2000:
            raise ValueError(f"Chunk exceeds maximum length: {len(self.text)} > 2000")
        
        if self.chunk_index < 0:
            raise ValueError("Chunk index must be non-negative")
        
        # Auto-detect table presence
        self.has_table = self._contains_table()
        
        # Auto-detect code block presence
        self.has_code_block = self._contains_code_block()
        
        # Extract section heading if not provided
        if self.section_heading is None:
            self.section_heading = self._extract_section_heading()
    
    def _contains_table(self) -> bool:
        """Check if chunk contains markdown table."""
        # Markdown table pattern: lines with pipes
        lines = self.text.split('\n')
        table_lines = [line for line in lines if '|' in line and line.strip().startswith('|')]
        return len(table_lines) >= 2  # At least header + one row
    
    def _contains_code_block(self) -> bool:
        """Check if chunk contains code block."""
        return '```' in self.text or '~~~' in self.text
    
    def _extract_section_heading(self) -> Optional[str]:
        """Extract first markdown heading from chunk."""
        lines = self.text.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                # Remove markdown heading syntax
                heading = re.sub(r'^#+\s*', '', line.strip())
                return heading[:100]  # Limit heading length
        return None
    
    def to_chromadb_format(self) -> tuple[str, str, dict]:
        """
        Convert chunk to ChromaDB format.
        
        Returns:
            (document_text, embedding_text, metadata)
        """
        metadata = {
            "datasheet_name": self.datasheet_name,
            "folder_path": self.folder_path,
            "chunk_index": self.chunk_index,
            "ingestion_timestamp": self.ingestion_timestamp,
            "has_table": self.has_table,
            "has_code_block": self.has_code_block,
        }
        
        if self.section_heading:
            metadata["section_heading"] = self.section_heading
        
        if self.image_paths:
            metadata["image_paths"] = self.image_paths
        
        if self.source_page_hint:
            metadata["source_page_hint"] = self.source_page_hint
        
        return (self.text, self.text, metadata)
```

#### Validation Rules

1. **Non-empty text**: Chunks must contain at least one non-whitespace character
2. **Length constraints**: Maximum 2000 characters (buffer above 1500 target for large tables)
3. **Index uniqueness**: Chunk indices must be unique within a datasheet's chunks
4. **Image path format**: All image paths must be absolute Windows paths
5. **Timestamp format**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`)

---

### 3. IngestionResult

Represents the outcome of ingesting a single datasheet.

#### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `datasheet_name` | `str` | Yes | Datasheet identifier |
| `status` | `IngestionStatus` | Yes | Outcome (success/error/skipped) |
| `chunks_created` | `int` | No | Number of chunks inserted (if successful) |
| `duration_seconds` | `float` | Yes | Time taken for ingestion |
| `error_message` | `str` | No | Error details (if status is error) |
| `skipped_reason` | `str` | No | Reason for skipping (if status is skipped) |

#### Python Model

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class IngestionResult:
    datasheet_name: str
    status: IngestionStatus
    duration_seconds: float
    chunks_created: Optional[int] = None
    error_message: Optional[str] = None
    skipped_reason: Optional[str] = None
    
    def is_success(self) -> bool:
        return self.status == IngestionStatus.SUCCESS
    
    def is_error(self) -> bool:
        return self.status == IngestionStatus.ERROR
    
    def is_skipped(self) -> bool:
        return self.status == IngestionStatus.SKIPPED
    
    def exceeded_performance_target(self) -> bool:
        """Check if ingestion exceeded 30-second target."""
        return self.duration_seconds > 30.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        result = {
            "datasheet_name": self.datasheet_name,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 2)
        }
        
        if self.chunks_created is not None:
            result["chunks_created"] = self.chunks_created
        
        if self.error_message:
            result["error_message"] = self.error_message
        
        if self.skipped_reason:
            result["skipped_reason"] = self.skipped_reason
        
        return result
```

---

### 4. BatchIngestionReport

Represents the summary of a complete ingestion batch.

#### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `total_datasheets` | `int` | Yes | Number of datasheets processed |
| `successful` | `int` | Yes | Number successfully ingested |
| `skipped` | `int` | Yes | Number skipped (already exist) |
| `failed` | `int` | Yes | Number failed with errors |
| `total_chunks` | `int` | Yes | Total chunks created |
| `total_duration_seconds` | `float` | Yes | Total processing time |
| `results` | `list[IngestionResult]` | Yes | Per-datasheet results |
| `start_timestamp` | `datetime` | Yes | Batch start time |
| `end_timestamp` | `datetime` | Yes | Batch end time |

#### Python Model

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class BatchIngestionReport:
    results: List[IngestionResult]
    start_timestamp: datetime
    end_timestamp: datetime
    
    @property
    def total_datasheets(self) -> int:
        return len(self.results)
    
    @property
    def successful(self) -> int:
        return sum(1 for r in self.results if r.is_success())
    
    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.is_skipped())
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.is_error())
    
    @property
    def total_chunks(self) -> int:
        return sum(r.chunks_created or 0 for r in self.results if r.chunks_created)
    
    @property
    def total_duration_seconds(self) -> float:
        return (self.end_timestamp - self.start_timestamp).total_seconds()
    
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_datasheets == 0:
            return 0.0
        return (self.successful / self.total_datasheets) * 100
    
    def exceeded_performance_targets(self) -> List[str]:
        """Return list of datasheets that exceeded 30-second target."""
        return [
            r.datasheet_name for r in self.results
            if r.is_success() and r.exceeded_performance_target()
        ]
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"{'='*60}",
            f"Ingestion Batch Summary",
            f"{'='*60}",
            f"Total Datasheets: {self.total_datasheets}",
            f"  ✅ Successful: {self.successful}",
            f"  ⏭️  Skipped: {self.skipped}",
            f"  ❌ Failed: {self.failed}",
            f"",
            f"Total Chunks Created: {self.total_chunks}",
            f"Total Duration: {self.total_duration_seconds:.2f} seconds",
            f"Success Rate: {self.success_rate():.1f}%",
        ]
        
        slow = self.exceeded_performance_targets()
        if slow:
            lines.append(f"\n⚠️  Slow Ingestions (>30s): {len(slow)}")
            for name in slow[:5]:  # Show first 5
                lines.append(f"  - {name}")
            if len(slow) > 5:
                lines.append(f"  ... and {len(slow) - 5} more")
        
        if self.failed > 0:
            lines.append(f"\n❌ Failed Datasheets:")
            for result in self.results:
                if result.is_error():
                    lines.append(f"  - {result.datasheet_name}: {result.error_message}")
        
        lines.append(f"{'='*60}")
        return '\n'.join(lines)
```

---

## Entity Relationships

```
┌─────────────────────┐
│   Datasheet         │
│  (Folder-based)     │
└──────────┬──────────┘
           │ 1
           │
           │ has
           │
           │ N
┌──────────▼──────────┐
│  ContentChunk       │
│  (Stored in         │
│   ChromaDB)         │
└─────────────────────┘

┌─────────────────────┐
│  IngestionResult    │
│  (Per-datasheet)    │
└──────────┬──────────┘
           │ N
           │
           │ aggregated into
           │
           │ 1
┌──────────▼──────────────┐
│ BatchIngestionReport    │
│ (Summary of batch)      │
└─────────────────────────┘
```

### Relationship Details

1. **Datasheet → ContentChunk** (1:N)
   - One datasheet produces multiple chunks (typically 5-50)
   - Chunks reference parent via `datasheet_name` (foreign key-like relationship)
   - Cascade delete: If datasheet re-ingested with `--force-update`, all chunks deleted first

2. **Datasheet → IngestionResult** (1:1)
   - Each datasheet produces one result per ingestion attempt
   - Result captures outcome and performance metrics

3. **IngestionResult → BatchIngestionReport** (N:1)
   - Batch report aggregates all results from single CLI invocation
   - Used for summary logging and success rate calculation

---

## State Transitions

### Datasheet Ingestion Lifecycle

```
┌─────────┐
│ PENDING │  (Initial state when discovered)
└────┬────┘
     │
     ▼
┌────────────┐
│ PROCESSING │  (Actively ingesting: parsing, chunking, embedding)
└────┬───────┘
     │
     ├──────────────────┬──────────────────┐
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────┐      ┌─────────┐      ┌───────┐
│ SUCCESS │      │  ERROR  │      │SKIPPED│
└─────────┘      └─────────┘      └───────┘
(chunks created)  (failed)       (already exists)
```

#### State Descriptions

- **PENDING**: Datasheet discovered in folder, waiting to be processed
- **PROCESSING**: Currently parsing markdown, chunking, generating embeddings, inserting into ChromaDB
- **SUCCESS**: All chunks successfully inserted into ChromaDB
- **ERROR**: Ingestion failed due to parsing error, ChromaDB error, or validation failure
- **SKIPPED**: Datasheet already exists in ChromaDB and `--force-update` not provided

#### Transition Triggers

| From | To | Trigger | Side Effects |
|------|----|---------| -------------|
| PENDING | PROCESSING | `start_ingestion()` | Log "Processing [name]..." |
| PROCESSING | SUCCESS | Chunks inserted successfully | Update chunk_count, log success |
| PROCESSING | ERROR | Exception raised | Capture error_message, log error |
| PROCESSING | SKIPPED | Duplicate detected and not force-update | Log skip reason |

#### Validation Rules by State

- **PENDING**: Must have valid folder_path and markdown_file_path
- **PROCESSING**: Must have ingestion_timestamp set
- **SUCCESS**: Must have chunk_count > 0 and duration_seconds > 0
- **ERROR**: Must have error_message populated
- **SKIPPED**: Must have chunk_count = None (not ingested)

---

## ChromaDB Schema

### Collection Configuration

```python
collection = client.get_or_create_collection(
    name="datasheets",
    metadata={
        "hnsw:space": "cosine",  # Cosine similarity for embeddings
        "description": "Electrical component datasheets for PCB design",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimensions": 384,
        "chunking_strategy": "two-stage-semantic",
        "chunk_size_target": 1500,
        "chunk_overlap_percent": 15,
        "schema_version": "1.0.0"
    }
)
```

### Document Storage Format

Each chunk stored in ChromaDB with:

```python
# IDs (auto-generated UUIDs)
ids = ["uuid-1", "uuid-2", ...]

# Documents (text content)
documents = [
    "# Electrical Characteristics\nVCC: 5V ± 10%...",
    "## Pin Configuration\n| Pin | Name | Function |...",
    ...
]

# Embeddings (auto-generated by ChromaDB)
embeddings = [
    [0.123, -0.456, ...],  # 384-dimensional vectors
    [0.789, 0.012, ...],
    ...
]

# Metadata (structured)
metadatas = [
    {
        "datasheet_name": "TL072",
        "folder_path": "D:\\datasheets\\TL072",
        "chunk_index": 0,
        "section_heading": "Electrical Characteristics",
        "has_table": True,
        "has_code_block": False,
        "image_paths": ["D:\\datasheets\\TL072\\images\\pinout.png"],
        "ingestion_timestamp": "2025-01-22T10:30:00Z"
    },
    ...
]
```

### Query Patterns for MCP Server

```python
# 1. Semantic search for component information
results = collection.query(
    query_texts=["op-amp input impedance specifications"],
    n_results=5,
    where={"has_table": True}  # Filter for chunks with tables
)

# 2. Get all chunks for a specific datasheet
results = collection.get(
    where={"datasheet_name": "TL072"}
)

# 3. Find datasheets with specific section
results = collection.query(
    query_texts=["pin configuration"],
    where={"section_heading": {"$contains": "Pin"}}
)
```

---

## Data Flow Diagram

```
┌──────────────────────┐
│ Input: Folder Path   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Discover Datasheets  │ (Scan for subfolders with .md files)
│  → List[Datasheet]   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Check Duplicates     │ (Query ChromaDB by datasheet_name)
└──────────┬───────────┘
           │
           ├───────────────────┐
           │                   │
           ▼                   ▼
    ┌──────────┐         ┌─────────┐
    │ Exists?  │         │ New?    │
    └────┬─────┘         └────┬────┘
         │                    │
         ▼                    ▼
   ┌──────────────┐     ┌──────────────┐
   │ force-update?│     │ Parse        │
   └───┬──────────┘     │ Markdown     │
       │                └───────┬──────┘
       │ Yes                    │
       ▼                        │
   ┌──────────────┐             │
   │ Delete old   │             │
   │ chunks       │             │
   └───┬──────────┘             │
       │                        │
       └────────────┬───────────┘
                    │
                    ▼
          ┌─────────────────┐
          │ Semantic Chunk  │ (Two-stage splitting)
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Resolve Image   │ (Convert relative → absolute paths)
          │ Paths           │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Create          │ (Instantiate ContentChunk objects)
          │ ContentChunks   │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Generate        │ (ChromaDB default: all-MiniLM-L6-v2)
          │ Embeddings      │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Insert into     │ (Batch insert to "datasheets" collection)
          │ ChromaDB        │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Create          │ (Record success/error/duration)
          │ IngestionResult │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Aggregate to    │ (Summary report)
          │ BatchReport     │
          └─────────────────┘
```

---

## Validation Rules Summary

### Pre-Ingestion Validation

1. ✅ Folder exists and is a directory
2. ✅ Folder contains exactly one `.md` file
3. ✅ Markdown file is readable (valid UTF-8)
4. ✅ Image paths (if referenced) resolve to existing files
5. ✅ Folder name is non-empty and valid

### During Ingestion Validation

1. ✅ Chunks are non-empty (at least 1 character)
2. ✅ Chunks do not exceed 2000 characters
3. ✅ Chunk indices are sequential (0, 1, 2, ...)
4. ✅ Image paths are absolute
5. ✅ Timestamps are ISO 8601 format

### Post-Ingestion Validation

1. ✅ At least one chunk created per datasheet
2. ✅ All chunks inserted into ChromaDB successfully
3. ✅ Chunk count matches expected number
4. ✅ Embeddings generated for all chunks
5. ✅ Metadata stored correctly

---

## Error Handling Strategy

### Recoverable Errors (Log warning, continue)

- Missing image file referenced in markdown
- Malformed table (use best-effort parsing)
- Missing section headers
- Large chunk (>1500 chars but <2000)

### Fatal Errors (Skip datasheet, log error)

- No markdown file in folder
- Multiple markdown files in folder
- Markdown file unreadable (encoding error)
- Chunk exceeds 2000 characters
- ChromaDB insertion failure

### Batch-Level Errors (Abort entire batch)

- ChromaDB connection failure
- Invalid folder path provided
- Insufficient disk space
- Permission denied on ChromaDB directory

---

## Performance Metrics

### Per-Datasheet Metrics

- `duration_seconds`: Total time from parse start to ChromaDB insert complete
- `chunk_count`: Number of chunks generated
- `chunks_per_second`: Throughput metric (chunk_count / duration_seconds)

### Batch-Level Metrics

- `total_duration_seconds`: Wall-clock time for entire batch
- `success_rate`: Percentage of successfully ingested datasheets
- `average_duration`: Mean duration per datasheet
- `average_chunks`: Mean chunks per datasheet
- `throughput`: Total chunks / total duration

### Performance Targets

| Metric | Target | Actual Behavior if Exceeded |
|--------|--------|----------------------------|
| Single datasheet | < 30 seconds | Log warning, continue |
| 100 datasheets | < 30 minutes | Log warning, continue |
| Success rate | ≥ 95% | No automatic action (manual review) |
| Table preservation | ≥ 90% intact | No automatic action (manual review) |

---

## Future Enhancements (Out of Scope for v1.0)

- **Component type auto-detection**: Parse markdown content to classify component (op-amp, MCU, resistor)
- **Source page tracking**: Extract page numbers from markdown comments for better provenance
- **Table splitting logic**: Intelligently split large tables while preserving headers
- **Incremental updates**: Detect changed chunks only (content hashing)
- **Collection sharding**: Split datasheets into multiple collections by type
- **Batch embedding**: Process 10-20 chunks at once for performance
- **Custom embedding models**: Support for domain-specific models (electrical engineering tuned)

---

## Summary

This data model supports the document-centric architecture required by the constitution:

✅ **Document provenance**: Folder path, ingestion timestamp, chunk position preserved  
✅ **Semantic chunking**: Two-stage strategy respects table and section boundaries  
✅ **ChromaDB schema**: Single collection with rich metadata for MCP server queries  
✅ **State management**: Clear lifecycle with validation at each transition  
✅ **Error recovery**: Graceful degradation with detailed logging  
✅ **Performance tracking**: Metrics at datasheet and batch level  

**Status**: Ready for contract definition (Phase 1 continues)
