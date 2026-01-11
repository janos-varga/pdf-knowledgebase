# Implementation Plan: Datasheet Ingestion Pipeline

**Branch**: `001-datasheet-ingestion-pipeline` | **Date**: 2025-01-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-datasheet-ingestion-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a LangChain-based CLI ingestion pipeline for electrical component datasheets in markdown format. The pipeline will parse markdown files with tables and images, perform semantic chunking that respects document structure, convert relative image paths to absolute paths, and store chunks with metadata in a persistent ChromaDB collection at `D:\.cache\chromadb`. The system will support incremental ingestion with duplicate detection and force-update capabilities, enabling engineers to build a searchable knowledge base for AI-assisted PCB design queries via Chroma MCP Server.

## Technical Context

**Language/Version**: Python 3.13  
**Build Tool**: uv (modern Python package manager and build tool)  
**Primary Dependencies**: 
- **LangChain**: langchain, langchain-community, langchain-chroma, langchain_text_splitters
- **ChromaDB**: chromadb (vector database with persistent storage)
- **Embeddings**: sentence-transformers (CPU-optimized), torch (CPU-only build)
- **CLI/Utilities**: argparse (stdlib), pathlib (stdlib), pyyaml, python-dotenv
- **Markdown**: markdown (parsing library)
- **Testing**: pytest, pytest-cov
- **Installation Note**: PyTorch CPU-only via `pip install torch --index-url https://download.pytorch.org/whl/cpu`

**Storage**: ChromaDB (persistent, self-hosted at `D:\.cache\chromadb\`, collection: "datasheets")  
**Testing**: pytest (unit tests for chunking logic, integration tests for ChromaDB operations)  
**Target Platform**: Windows (primary), CPU-only processing (no GPU dependencies)  
**Project Type**: Single CLI application  
**Performance Goals**: 
- 20-page datasheet ingestion < 30 seconds (target, warning if exceeded)
- 100 datasheets (avg 15 pages) < 30 minutes
- Single page processing < 5 seconds for text-based markdown

**Constraints**: 
- Must use Windows-compatible path handling (pathlib, avoid Unix-specific separators)
- CPU-only embeddings (no CUDA/GPU libraries)
- Must be compatible with Chroma MCP Server's query interface (metadata schema alignment)
- No external API calls during ingestion (local embedding models only)
- Maximum chunk size: 1500 characters to prevent embedding model truncation
- Chunk overlap: 15% (approximately 225 characters)

**Scale/Scope**: 
- Initial target: 100-200 datasheets per engineer
- Scaling to 10,000+ chunks in single collection
- Average datasheet: 15-20 pages, 5-10 tables, 3-8 images
- Folder-based organization (one subfolder per datasheet)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Document-Centric Architecture
✅ **COMPLIANT** - Pipeline preserves complete document provenance:
- Source folder path stored in metadata
- Folder name serves as datasheet identifier
- Absolute image paths maintained
- Chunk index and section context preserved
- Domain-specific metadata (electrical engineering) supported

### Principle II: ChromaDB as Single Source of Truth
✅ **COMPLIANT** - ChromaDB is the sole storage system:
- Single persistent collection ("datasheets") at `D:\.cache\chromadb\`
- No duplicate storage or intermediate databases
- Metadata schema designed for MCP server access patterns
- Collection organized by document type (all datasheets in one collection)
- Default embedding function with version tracking in collection metadata

### Principle III: Semantic Chunking Over Fixed-Size
✅ **COMPLIANT** - Two-stage semantic chunking strategy:
- ExperimentalMarkdownSyntaxTextSplitter preserves markdown structure (strip_headers=False)
- RecursiveCharacterTextSplitter for intelligent splitting within markdown groups
- Tables and code blocks kept intact (prioritized over section boundaries if needed)
- Chunk overlap (15%) maintains cross-reference context
- Metadata includes chunk position, parent document, section hierarchy
- Target chunk size: 1500 characters to prevent truncation

### Principle IV: Observability and Quality Metrics
✅ **COMPLIANT** - Comprehensive logging and monitoring:
- Per-datasheet status logging (success/skip/error)
- Ingestion timing tracked (warning if >30 seconds)
- Structured logging for chunk generation, embedding, ChromaDB insertion
- CLI output provides human-readable summary
- Metadata includes ingestion timestamp and chunk counts
- Error messages include folder path and actionable details

**Constitution Compliance**: ✅ **ALL GATES PASSED (4/4 principles)** - No violations requiring justification.

**Phase 1 Re-check**: ✅ **ALL GATES REMAIN COMPLIANT (4/4 principles)**
- Data model preserves document provenance (folder_path, chunk_index, section_heading)
- ChromaDB metadata schema supports MCP server query patterns
- Contract definitions maintain constitutional principles
- No additional violations introduced during design phase

## Project Structure

### Documentation (this feature)

```text
specs/001-datasheet-ingestion-pipeline/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (technology choices, best practices)
├── data-model.md        # Phase 1 output (entities, relationships, state)
├── quickstart.md        # Phase 1 output (usage examples, common workflows)
├── contracts/           # Phase 1 output (CLI interface, metadata schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── ingestion/
│   ├── __init__.py
│   ├── pipeline.py          # Main ingestion orchestrator
│   ├── chunker.py           # Semantic chunking logic
│   ├── markdown_parser.py   # Markdown parsing and image path resolution
│   └── chroma_client.py     # ChromaDB operations (insert, check, delete)
├── models/
│   ├── __init__.py
│   ├── datasheet.py         # Datasheet entity
│   └── chunk.py             # Content chunk entity
├── cli/
│   ├── __init__.py
│   └── ingest.py            # CLI entry point (argparse)
└── utils/
    ├── __init__.py
    ├── logger.py            # Structured logging configuration
    └── validators.py        # Folder structure validation

tests/
├── unit/
│   ├── test_chunker.py
│   ├── test_markdown_parser.py
│   └── test_validators.py
├── integration/
│   ├── test_pipeline.py
│   └── test_chroma_client.py
└── fixtures/
    └── sample_datasheets/   # Test markdown files

# Additional files at repository root
requirements.txt             # Python dependencies
README.md                    # Project overview and setup
pyproject.toml              # Build configuration and tool settings
```

**Structure Decision**: Single project structure chosen because this is a focused CLI tool with no frontend/backend separation or mobile components. All ingestion logic lives in `src/ingestion/`, with clear separation between parsing (markdown_parser), chunking (chunker), storage (chroma_client), and orchestration (pipeline). The `cli/` module provides the command-line interface, while `models/` defines domain entities. This structure aligns with Python best practices and supports the constitution's emphasis on document-centric architecture.

## Complexity Tracking

> **Not applicable** - All Constitution Check gates passed with no violations requiring justification.

---

## Phase Completion Status

### ✅ Phase 0: Outline & Research (COMPLETE)

**Artifacts Generated**:
- ✅ `research.md` - Technology choices, best practices, risk analysis

**Key Decisions**:
- Chunking strategy: Two-stage (ExperimentalMarkdownSyntaxTextSplitter + RecursiveCharacterTextSplitter)
- Embedding model: ChromaDB default (sentence-transformers/all-MiniLM-L6-v2)
- Path handling: pathlib.Path for Windows compatibility
- Duplicate detection: Metadata filtering on folder name
- CLI framework: argparse with structured error handling

**Research Areas Resolved**:
1. ✅ Semantic chunking strategy for markdown documents
2. ✅ ChromaDB embedding function for CPU-only environments
3. ✅ Windows path handling best practices
4. ✅ Duplicate detection strategy for ChromaDB
5. ✅ CLI argument parsing and error handling
6. ✅ Additional Python libraries required
7. ✅ Logging strategy
8. ✅ Performance optimization strategies
9. ✅ Testing strategy
10. ✅ Risk analysis and mitigation

---

### ✅ Phase 1: Design & Contracts (COMPLETE)

**Artifacts Generated**:
- ✅ `data-model.md` - Entities, relationships, validation rules, state transitions
- ✅ `contracts/cli-interface.md` - Command-line interface specification
- ✅ `contracts/chromadb-metadata-schema.md` - ChromaDB metadata schema and query patterns
- ✅ `quickstart.md` - Usage examples and common workflows
- ✅ `.github/agents/copilot-instructions.md` - Updated with technology stack
- ✅ `requirements.txt` - Updated with additional dependencies

**Design Artifacts**:

1. **Data Model**:
   - 4 core entities: Datasheet, ContentChunk, IngestionResult, BatchIngestionReport
   - Complete validation rules and state transitions
   - ChromaDB collection schema with metadata format
   - Query patterns for MCP Server integration

2. **CLI Contract**:
   - Command: `python -m src.cli.ingest <folder> [--force-update] [--log-level LEVEL]`
   - Exit codes: 0 (success), 1 (validation), 2 (ChromaDB), 3 (ingestion)
   - Dual logging: Console (human-readable) + JSON file (structured)
   - Environment variables: CHROMADB_PATH, CHROMADB_COLLECTION

3. **ChromaDB Schema**:
   - Collection: "datasheets"
   - Required metadata: datasheet_name, folder_path, chunk_index, ingestion_timestamp, has_table, has_code_block
   - Optional metadata: section_heading, image_paths, source_page_hint
   - Query patterns for semantic search, filtered search, datasheet retrieval

4. **Quickstart Guide**:
   - Prerequisites and setup instructions
   - Common workflows (new ingestion, updates, troubleshooting, batch processing)
   - Usage examples and PowerShell integration scripts
   - FAQ and troubleshooting section

**Constitution Re-Check**: ✅ All principles remain compliant after design phase

---

### ⏭️ Phase 2: Task Generation (NOT STARTED)

**Note**: Phase 2 (task breakdown) is handled by the `/speckit.tasks` command, which is separate from the `/speckit.plan` command. This plan document provides the foundation for task generation.

**Expected Output**: `tasks.md` with dependency-ordered implementation tasks

---

## Implementation Readiness

### ✅ Planning Complete

All design artifacts are ready for implementation:

1. ✅ **Technical unknowns resolved** - Research phase completed
2. ✅ **Data model defined** - Entities, relationships, validation rules
3. ✅ **Contracts specified** - CLI interface and ChromaDB schema
4. ✅ **Usage documented** - Quickstart guide with examples
5. ✅ **Dependencies updated** - requirements.txt includes all libraries
6. ✅ **Agent context updated** - GitHub Copilot instructions current
7. ✅ **Constitution compliant** - All gates passed (pre and post design)

### 📋 Next Steps

1. **Run `/speckit.tasks`** to generate dependency-ordered implementation tasks
2. **Create source code structure** according to plan (src/, tests/, etc.)
3. **Implement core modules** following task order
4. **Write tests** (unit and integration) as specified in research phase
5. **Validate with sample datasheets** per quickstart guide

---

## Summary

**Feature**: Datasheet Ingestion Pipeline  
**Branch**: `001-datasheet-ingestion-pipeline`  
**Status**: ✅ **DESIGN COMPLETE** - Ready for task generation and implementation  

**Deliverables**:
- 📄 Implementation plan (this document)
- 🔬 Research report with 10 resolved technology decisions
- 🏗️ Data model with 4 entities and complete schemas
- 📜 CLI contract with detailed interface specification
- 🗄️ ChromaDB metadata schema with query patterns
- 🚀 Quickstart guide with usage examples
- 📦 Updated requirements.txt
- 🤖 Updated agent context file

**Constitution Compliance**: ✅ **FULL COMPLIANCE** (7 checks passing)  
**Performance Targets**: Defined and achievable (30s per datasheet, 30min for 100)  
**Risk Mitigation**: Documented with graceful degradation strategies  

**Command to proceed**: `Run /speckit.tasks to generate implementation tasks`
