# ChromaDB Metadata Schema

**Feature**: 001-datasheet-ingestion-pipeline  
**Date**: 2025-01-22  
**Version**: 1.0.0

## Overview

This document defines the metadata schema for chunks stored in ChromaDB, ensuring compatibility with Chroma MCP Server queries and maintaining document provenance as required by the project constitution.

---

## Collection Configuration

### Collection Name

**Name**: `datasheets`  
**Type**: Persistent collection  
**Path**: `D:\.cache\chromadb` (default, configurable via `CHROMADB_PATH`)

### Collection Metadata

Stored once at collection creation to track schema versioning and configuration.

```python
collection_metadata = {
    # Distance metric for similarity search
    "hnsw:space": "cosine",  # Options: cosine, l2, ip (inner product)
    
    # Descriptive metadata
    "description": "Electrical component datasheets for PCB design",
    "domain": "electrical_engineering",
    "project": "pdf-knowledgebase",
    
    # Embedding configuration
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimensions": 384,
    "embedding_provider": "chromadb_default",
    
    # Chunking strategy metadata
    "chunking_strategy": "two-stage-semantic",
    "chunking_stage1": "ExperimentalMarkdownSyntaxTextSplitter",
    "chunking_stage2": "RecursiveCharacterTextSplitter",
    "chunk_size_target": 1500,
    "chunk_overlap_percent": 15,
    "chunk_overlap_chars": 225,
    
    # Schema version for migration tracking
    "schema_version": "1.0.0",
    "created_at": "2025-01-22T10:00:00Z",
    "last_modified": "2025-01-22T10:00:00Z"
}
```

### Collection Creation Code

```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path=r"D:\.cache\chromadb",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=False  # Prevent accidental data loss
    )
)

collection = client.get_or_create_collection(
    name="datasheets",
    metadata=collection_metadata
)
```

---

## Chunk Metadata Schema

Each chunk stored in ChromaDB has associated metadata following this schema:

### Required Fields

| Field | Type | Description | Example | Constraints |
|-------|------|-------------|---------|-------------|
| `datasheet_name` | `str` | Unique datasheet identifier (folder name) | `"TL072"` | Non-empty, no path separators |
| `folder_path` | `str` | Absolute path to datasheet folder | `"D:\\datasheets\\TL072"` | Valid Windows path |
| `chunk_index` | `int` | Sequential chunk number within datasheet | `0`, `1`, `2`, ... | ≥ 0, unique per datasheet |
| `ingestion_timestamp` | `str` | ISO 8601 timestamp of ingestion | `"2025-01-22T10:30:00Z"` | UTC timezone |
| `has_table` | `bool` | Flag indicating table presence | `true`, `false` | Boolean |
| `has_code_block` | `bool` | Flag indicating code block presence | `true`, `false` | Boolean |

### Optional Fields

| Field | Type | Description | Example | Constraints |
|-------|------|-------------|---------|-------------|
| `section_heading` | `str` | Markdown section heading | `"Electrical Characteristics"` | ≤ 100 characters |
| `image_paths` | `list[str]` | Absolute paths to images in chunk | `["D:\\datasheets\\TL072\\pinout.png"]` | Valid file paths |
| `source_page_hint` | `int` | Approximate source page number | `5` | ≥ 1 (future) |
| `component_type` | `str` | Component category | `"op-amp"` | Future enhancement |
| `contains_formula` | `bool` | Flag for mathematical formulae | `true` | Future enhancement |

---

## Metadata Examples

### Example 1: Text Chunk with Section Heading

```python
metadata = {
    "datasheet_name": "TL072",
    "folder_path": "D:\\datasheets\\TL072",
    "chunk_index": 0,
    "ingestion_timestamp": "2025-01-22T10:30:00Z",
    "has_table": False,
    "has_code_block": False,
    "section_heading": "General Description"
}

# Corresponding document text
document = """
# General Description

The TL072 is a high-performance dual JFET-input operational amplifier. 
It features low noise, high input impedance, and wide bandwidth, making it 
ideal for audio and instrumentation applications.
"""
```

### Example 2: Chunk with Table

```python
metadata = {
    "datasheet_name": "TL072",
    "folder_path": "D:\\datasheets\\TL072",
    "chunk_index": 3,
    "ingestion_timestamp": "2025-01-22T10:30:00Z",
    "has_table": True,
    "has_code_block": False,
    "section_heading": "Electrical Characteristics"
}

document = """
## Electrical Characteristics

| Parameter | Min | Typ | Max | Unit |
|-----------|-----|-----|-----|------|
| Supply Voltage | ±4 | ±15 | ±18 | V |
| Input Offset Voltage | - | 3 | 10 | mV |
| Input Bias Current | - | 30 | 200 | pA |
| Gain Bandwidth Product | - | 3 | - | MHz |
"""
```

### Example 3: Chunk with Images

```python
metadata = {
    "datasheet_name": "TL072",
    "folder_path": "D:\\datasheets\\TL072",
    "chunk_index": 1,
    "ingestion_timestamp": "2025-01-22T10:30:00Z",
    "has_table": False,
    "has_code_block": False,
    "section_heading": "Pin Configuration",
    "image_paths": [
        "D:\\datasheets\\TL072\\pinout.png",
        "D:\\datasheets\\TL072\\package.png"
    ]
}

document = """
## Pin Configuration

The TL072 is available in 8-pin DIP and SOIC packages.

![Pinout Diagram](./pinout.png)

![Package Dimensions](./package.png)

| Pin | Name | Function |
|-----|------|----------|
| 1   | OUT1 | Output 1 |
| 2   | IN1- | Inverting Input 1 |
| 3   | IN1+ | Non-inverting Input 1 |
| 4   | VCC- | Negative Supply |
"""
```

### Example 4: Chunk with Code Block

```python
metadata = {
    "datasheet_name": "ATmega328P",
    "folder_path": "D:\\datasheets\\ATmega328P",
    "chunk_index": 15,
    "ingestion_timestamp": "2025-01-22T10:45:00Z",
    "has_table": False,
    "has_code_block": True,
    "section_heading": "Timer Configuration Example"
}

document = """
## Timer Configuration Example

Configure Timer1 for 1 Hz interrupt:

```c
// Set prescaler to 1024
TCCR1B |= (1 << CS12) | (1 << CS10);

// Enable CTC mode
TCCR1B |= (1 << WGM12);

// Set compare value for 1 Hz @ 16 MHz
OCR1A = 15624;

// Enable compare interrupt
TIMSK1 |= (1 << OCIE1A);
```
"""
```

---

## Storage Format in ChromaDB

### Complete Chunk Structure

Each chunk stored with four components:

```python
# 1. ID (auto-generated UUID by ChromaDB)
chunk_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# 2. Document (text content)
document = "# Electrical Characteristics\nVCC: 5V ± 10%..."

# 3. Embedding (384-dimensional vector, auto-generated)
embedding = [0.123, -0.456, 0.789, ..., 0.012]  # 384 floats

# 4. Metadata (dictionary)
metadata = {
    "datasheet_name": "TL072",
    "folder_path": "D:\\datasheets\\TL072",
    "chunk_index": 3,
    "ingestion_timestamp": "2025-01-22T10:30:00Z",
    "has_table": True,
    "has_code_block": False,
    "section_heading": "Electrical Characteristics"
}
```

### Batch Insert Code

```python
# Prepare batch data
ids = [f"{datasheet.name}_chunk_{i}" for i in range(len(chunks))]
documents = [chunk.text for chunk in chunks]
metadatas = [chunk.to_chromadb_metadata() for chunk in chunks]

# Insert into ChromaDB (embeddings auto-generated)
collection.add(
    ids=ids,
    documents=documents,
    metadatas=metadatas
)
```

---

## Query Patterns for MCP Server

### 1. Semantic Search (Basic)

**Use Case**: Find relevant information about a component or concept

```python
results = collection.query(
    query_texts=["op-amp input impedance specifications"],
    n_results=5
)

# Returns:
# {
#   'ids': [['TL072_chunk_3', 'LM358_chunk_5', ...]],
#   'distances': [[0.23, 0.34, ...]],
#   'documents': [['## Electrical Characteristics\n...', ...]],
#   'metadatas': [[
#       {'datasheet_name': 'TL072', 'has_table': True, ...},
#       ...
#   ]]
# }
```

### 2. Filtered Search by Datasheet

**Use Case**: Search within a specific datasheet only

```python
results = collection.query(
    query_texts=["pin configuration"],
    n_results=10,
    where={"datasheet_name": "TL072"}
)
```

### 3. Find Chunks with Tables

**Use Case**: Locate specification tables across all datasheets

```python
results = collection.query(
    query_texts=["maximum ratings"],
    n_results=10,
    where={"has_table": True}
)
```

### 4. Find Chunks with Code Examples

**Use Case**: Locate code snippets for microcontroller configuration

```python
results = collection.query(
    query_texts=["timer configuration"],
    n_results=5,
    where={"has_code_block": True}
)
```

### 5. Retrieve All Chunks for a Datasheet

**Use Case**: Get complete datasheet content for context

```python
results = collection.get(
    where={"datasheet_name": "TL072"},
    include=["documents", "metadatas"]
)

# Sort by chunk_index to reconstruct order
sorted_chunks = sorted(
    zip(results['documents'], results['metadatas']),
    key=lambda x: x[1]['chunk_index']
)
```

### 6. Find Recent Ingestions

**Use Case**: Identify newly added datasheets

```python
from datetime import datetime, timedelta

# Calculate timestamp for "last 7 days"
cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

results = collection.get(
    where={
        "ingestion_timestamp": {"$gte": cutoff}
    }
)

# Extract unique datasheet names
recent_datasheets = set(
    meta['datasheet_name'] for meta in results['metadatas']
)
```

### 7. Find Chunks with Images

**Use Case**: Locate chunks that reference diagrams or schematics

```python
results = collection.query(
    query_texts=["schematic diagram"],
    n_results=10,
    where={
        "$and": [
            {"image_paths": {"$ne": []}},  # Has images
            {"section_heading": {"$contains": "Pin"}}  # Pin-related
        ]
    }
)
```

### 8. Complex Multi-Filter Search

**Use Case**: Advanced search combining multiple criteria

```python
# Find tables in "Electrical Characteristics" sections
# from datasheets ingested in last 30 days
results = collection.query(
    query_texts=["voltage ratings current limits"],
    n_results=20,
    where={
        "$and": [
            {"has_table": True},
            {"section_heading": {"$contains": "Electrical"}},
            {"ingestion_timestamp": {"$gte": "2024-12-23T00:00:00Z"}}
        ]
    }
)
```

---

## Metadata Indexing Strategy

### Indexed Fields (for Performance)

ChromaDB automatically indexes these fields for efficient filtering:

- `datasheet_name` (string equality, most common filter)
- `has_table` (boolean filter)
- `has_code_block` (boolean filter)
- `chunk_index` (integer range queries)

### Non-Indexed Fields (Full Scan)

These fields require collection scan (slower, avoid in large collections):

- `section_heading` (string contains, partial match)
- `image_paths` (list membership)
- `folder_path` (string equality, rarely used)

### Query Performance Guidelines

| Query Type | Indexed | Performance | Recommended Collection Size |
|------------|---------|-------------|---------------------------|
| Exact `datasheet_name` match | ✅ Yes | O(log n) | Unlimited |
| Boolean flags (`has_table`) | ✅ Yes | O(log n) | Unlimited |
| Integer range (`chunk_index`) | ✅ Yes | O(log n) | Unlimited |
| String contains (`section_heading`) | ❌ No | O(n) | < 100k chunks |
| List membership (`image_paths`) | ❌ No | O(n) | < 50k chunks |

---

## Metadata Validation Rules

### Field Constraints

```python
from typing import TypedDict, Optional, List

class ChunkMetadata(TypedDict):
    # Required fields
    datasheet_name: str           # Non-empty, max 255 chars
    folder_path: str              # Valid Windows path
    chunk_index: int              # >= 0
    ingestion_timestamp: str      # ISO 8601 format
    has_table: bool               # true or false
    has_code_block: bool          # true or false
    
    # Optional fields
    section_heading: Optional[str]      # Max 100 chars
    image_paths: Optional[List[str]]    # List of valid paths
    source_page_hint: Optional[int]     # >= 1

def validate_metadata(metadata: dict) -> None:
    """Validate metadata before ChromaDB insertion."""
    
    # Required field checks
    assert "datasheet_name" in metadata, "Missing datasheet_name"
    assert len(metadata["datasheet_name"]) > 0, "datasheet_name cannot be empty"
    assert len(metadata["datasheet_name"]) <= 255, "datasheet_name too long"
    
    assert "folder_path" in metadata, "Missing folder_path"
    assert "chunk_index" in metadata, "Missing chunk_index"
    assert metadata["chunk_index"] >= 0, "chunk_index must be non-negative"
    
    assert "ingestion_timestamp" in metadata, "Missing ingestion_timestamp"
    # ISO 8601 validation
    try:
        datetime.fromisoformat(metadata["ingestion_timestamp"].replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid timestamp format (expected ISO 8601)")
    
    assert "has_table" in metadata, "Missing has_table"
    assert isinstance(metadata["has_table"], bool), "has_table must be boolean"
    
    assert "has_code_block" in metadata, "Missing has_code_block"
    assert isinstance(metadata["has_code_block"], bool), "has_code_block must be boolean"
    
    # Optional field checks
    if "section_heading" in metadata and metadata["section_heading"]:
        assert len(metadata["section_heading"]) <= 100, "section_heading too long"
    
    if "image_paths" in metadata:
        assert isinstance(metadata["image_paths"], list), "image_paths must be list"
        for path in metadata["image_paths"]:
            assert isinstance(path, str), "image_path must be string"
    
    if "source_page_hint" in metadata:
        assert metadata["source_page_hint"] >= 1, "source_page_hint must be >= 1"
```

---

## Migration Strategy (Future Schema Changes)

### Version 1.0.0 → 2.0.0 Example

**Scenario**: Add new field `component_type` in v2.0

```python
def migrate_v1_to_v2(collection):
    """Add component_type field to existing chunks."""
    
    # Get all chunks
    all_chunks = collection.get(include=["metadatas"])
    
    # Update metadata
    updated_metadatas = []
    for metadata in all_chunks['metadatas']:
        if "component_type" not in metadata:
            # Infer from datasheet_name (simple heuristic)
            metadata["component_type"] = infer_component_type(
                metadata["datasheet_name"]
            )
        updated_metadatas.append(metadata)
    
    # Update collection metadata
    collection.modify(
        metadata={
            **collection.metadata,
            "schema_version": "2.0.0",
            "last_modified": datetime.utcnow().isoformat() + "Z"
        }
    )
    
    # ChromaDB update (delete and re-add with new metadata)
    collection.delete(ids=all_chunks['ids'])
    collection.add(
        ids=all_chunks['ids'],
        documents=all_chunks['documents'],
        embeddings=all_chunks['embeddings'],
        metadatas=updated_metadatas
    )
```

### Backward Compatibility

- **Minor version changes** (1.0 → 1.1): Add optional fields only, no breaking changes
- **Major version changes** (1.0 → 2.0): May add required fields or change field types, requires migration

---

## Metadata Size Considerations

### Size Limits

| Component | Size Limit | Notes |
|-----------|------------|-------|
| Metadata per chunk | ~10 KB | Recommended, no hard limit in ChromaDB |
| `datasheet_name` | 255 chars | Database indexing efficiency |
| `section_heading` | 100 chars | Display purposes |
| `image_paths` list | 50 items | Typical datasheet has < 10 images per chunk |
| Total collection | Unlimited | ChromaDB scales to millions of chunks |

### Size Optimization Tips

1. **Use short datasheet names**: Prefer `"TL072"` over `"Texas_Instruments_TL072_JFET_OpAmp_Datasheet_Rev_G"`
2. **Truncate long headings**: Store first 100 characters only
3. **Avoid redundant fields**: Don't duplicate information already in document text
4. **Use boolean flags**: More efficient than string tags (`has_table: true` vs `tags: ["table"]`)

---

## ChromaDB Compatibility Notes

### Supported ChromaDB Versions

**Minimum**: 0.4.22  
**Tested**: 0.4.24, 0.5.0  
**Recommended**: Latest stable release

### ChromaDB Metadata Limitations

- **No nested objects**: Metadata must be flat dictionary (no nested dicts)
  - ❌ `{"image": {"path": "...", "type": "png"}}`
  - ✅ `{"image_path": "...", "image_type": "png"}`

- **List types**: Only lists of strings supported
  - ✅ `image_paths: ["path1", "path2"]`
  - ❌ `image_paths: [{"path": "path1"}, {"path": "path2"}]`

- **Date/time**: Must be stored as strings (ISO 8601)
  - ✅ `ingestion_timestamp: "2025-01-22T10:30:00Z"`
  - ❌ `ingestion_timestamp: datetime(2025, 1, 22, 10, 30, 0)`

### Query Language Operators

ChromaDB supports these operators in `where` filters:

| Operator | Example | Description |
|----------|---------|-------------|
| `$eq` | `{"field": {"$eq": "value"}}` | Equal (can omit `$eq`) |
| `$ne` | `{"field": {"$ne": "value"}}` | Not equal |
| `$gt` | `{"field": {"$gt": 10}}` | Greater than |
| `$gte` | `{"field": {"$gte": 10}}` | Greater than or equal |
| `$lt` | `{"field": {"$lt": 10}}` | Less than |
| `$lte` | `{"field": {"$lte": 10}}` | Less than or equal |
| `$in` | `{"field": {"$in": ["a", "b"]}}` | In list |
| `$nin` | `{"field": {"$nin": ["a", "b"]}}` | Not in list |
| `$and` | `{"$and": [{...}, {...}]}` | Logical AND |
| `$or` | `{"$or": [{...}, {...}]}` | Logical OR |

**Note**: String contains (`$contains`) is not supported in ChromaDB v0.4.x; use semantic search instead.

---

## MCP Server Integration Contract

### Expected Metadata Fields (for Chroma MCP Server)

The Chroma MCP Server expects these fields for optimal query performance:

1. **Document identifier**: `datasheet_name` (string)
2. **Source tracking**: `folder_path` (string)
3. **Content flags**: `has_table`, `has_code_block` (boolean)
4. **Provenance**: `ingestion_timestamp` (ISO 8601 string)

### Recommended Query Patterns for MCP Server

```python
# Pattern 1: Semantic search with result filtering
def search_datasheets(query: str, filter_tables: bool = False):
    where_clause = {"has_table": True} if filter_tables else None
    return collection.query(
        query_texts=[query],
        n_results=10,
        where=where_clause
    )

# Pattern 2: Get full datasheet context
def get_datasheet_chunks(datasheet_name: str):
    results = collection.get(
        where={"datasheet_name": datasheet_name}
    )
    # Sort by chunk_index
    return sorted(
        zip(results['documents'], results['metadatas']),
        key=lambda x: x[1]['chunk_index']
    )

# Pattern 3: Find similar datasheets
def find_similar_datasheets(datasheet_name: str, n_results: int = 5):
    # Get representative chunk from target datasheet
    target_chunk = collection.get(
        where={
            "$and": [
                {"datasheet_name": datasheet_name},
                {"chunk_index": 0}  # Use first chunk
            ]
        },
        limit=1
    )
    
    # Find similar chunks from other datasheets
    if target_chunk['documents']:
        return collection.query(
            query_texts=[target_chunk['documents'][0]],
            n_results=n_results,
            where={"datasheet_name": {"$ne": datasheet_name}}
        )
```

---

## Summary

**Schema Version**: 1.0.0  
**Collection Name**: `datasheets`  
**Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)  
**Distance Metric**: Cosine similarity  
**Required Metadata**: `datasheet_name`, `folder_path`, `chunk_index`, `ingestion_timestamp`, `has_table`, `has_code_block`  
**Optional Metadata**: `section_heading`, `image_paths`, `source_page_hint`  
**Query Patterns**: Semantic search, filtered search, datasheet-specific retrieval  
**MCP Server**: Compatible with expected metadata schema  

**Status**: Ready for implementation
