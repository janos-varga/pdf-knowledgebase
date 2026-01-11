# Tasks: Datasheet Ingestion Pipeline

**Feature**: 001-datasheet-ingestion-pipeline  
**Input**: Design documents from `/specs/001-datasheet-ingestion-pipeline/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/  
**Generated**: 2025-01-22

**Tests**: No tests requested in specification - focusing on implementation tasks only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure per plan.md

- [X] T001 Create project directory structure: src/ingestion/, src/models/, src/cli/, src/utils/, tests/unit/, tests/integration/, tests/fixtures/
- [X] T002 Initialize Python project with uv: create pyproject.toml with build configuration and dependencies (migrate from requirements.txt)
- [X] T003 Install PyTorch CPU-only: uv pip install torch --index-url https://download.pytorch.org/whl/cpu
- [X] T004 Install core dependencies with uv: uv pip install chromadb langchain langchain-chroma langchain-community langchain_text_splitters sentence-transformers pytest pytest-cov markdown python-dotenv pyyaml
- [X] T005 [P] Create empty __init__.py files in all source packages: src/__init__.py, src/ingestion/__init__.py, src/models/__init__.py, src/cli/__init__.py, src/utils/__init__.py
- [X] T006 [P] Create .logs/ directory for structured JSON logging output
- [X] T007 [P] Create ChromaDB default directory: D:\.cache\chromadb (Windows-specific path)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 [P] Implement structured logging configuration in src/utils/logger.py with console (human-readable) and file (JSON) handlers
- [X] T009 [P] Implement folder structure validators in src/utils/validators.py (validate_folder_path, validate_datasheet_folder)
- [X] T010 [P] Create IngestionStatus enum in src/models/__init__.py (PENDING, PROCESSING, SUCCESS, ERROR, SKIPPED)
- [X] T011 [P] Create Datasheet model in src/models/datasheet.py with validation, from_folder() factory method, and state management
- [X] T012 [P] Create ContentChunk model in src/models/chunk.py with metadata extraction (_contains_table, _contains_code_block, _extract_section_heading), validation, and to_chromadb_format() method
- [X] T013 [P] Create IngestionResult model in src/models/datasheet.py with success/error/skipped status tracking and performance metrics
- [X] T014 [P] Create BatchIngestionReport model in src/models/datasheet.py with aggregation properties and summary() method
- [X] T015 Create ChromaDB client wrapper in src/ingestion/chroma_client.py with collection initialization, metadata schema, and connection handling

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Initial Datasheet Import (Priority: P1) 🎯 MVP

**Goal**: Enable engineers to import datasheet collections from markdown folders into ChromaDB for the first time with proper semantic chunking and metadata

**Independent Test**: Provide a folder path containing sample datasheets and verify they are successfully ingested into ChromaDB with proper metadata (datasheet_name, folder_path, chunk_index, has_table, has_code_block) and semantic chunking that keeps tables intact

### Implementation for User Story 1

- [ ] T016 [P] [US1] Implement markdown parser in src/ingestion/markdown_parser.py with UTF-8 file reading and basic validation
- [ ] T017 [P] [US1] Implement image path resolution in src/ingestion/markdown_parser.py (resolve_image_path function) to convert relative paths to absolute Windows paths
- [ ] T018 [US1] Implement two-stage semantic chunker in src/ingestion/chunker.py: Stage 1 with ExperimentalMarkdownSyntaxTextSplitter (strip_headers=False), Stage 2 with RecursiveCharacterTextSplitter (chunk_size=1500, overlap=225)
- [ ] T019 [US1] Add table and code block preservation logic in src/ingestion/chunker.py to ensure they remain intact within single chunks
- [ ] T020 [US1] Implement ChromaDB operations in src/ingestion/chroma_client.py: insert_chunks() for batch insertion with embeddings
- [ ] T021 [US1] Implement datasheet discovery in src/ingestion/pipeline.py: discover_datasheets() to scan folder for subfolders with .md files
- [ ] T022 [US1] Implement single datasheet ingestion in src/ingestion/pipeline.py: ingest_datasheet() orchestrating parse → chunk → embed → store
- [ ] T023 [US1] Implement batch ingestion orchestrator in src/ingestion/pipeline.py: ingest_batch() with error handling and progress logging
- [ ] T024 [US1] Implement CLI argument parsing in src/cli/ingest.py with argparse: datasheets_folder_path (required), --force-update (optional), --log-level (optional, choices: DEBUG/INFO/WARNING/ERROR, default INFO)
- [ ] T025 [US1] Implement CLI main() function in src/cli/ingest.py with exit codes (0=success, 1=validation error, 2=ChromaDB error, 3=ingestion error)
- [ ] T026 [US1] Add console output formatting in src/cli/ingest.py: header banner, per-datasheet progress, batch summary report
- [ ] T027 [US1] Add performance tracking in src/ingestion/pipeline.py: timing per datasheet, warning when exceeding 30-second target
- [ ] T028 [US1] Add environment variable support in src/cli/ingest.py for CHROMADB_PATH and CHROMADB_COLLECTION with defaults (D:\.cache\chromadb, datasheets)

**Checkpoint**: At this point, User Story 1 should be fully functional - engineers can run `python -m src.cli.ingest <folder>` and successfully ingest new datasheets into ChromaDB

---

## Phase 4: User Story 2 - Incremental Updates (Priority: P2)

**Goal**: Enable engineers to update specific datasheets without re-ingesting the entire collection, supporting efficient maintenance workflows

**Independent Test**: Ingest a datasheet, modify it, run ingestion with --force-update flag, and verify the updated content replaces the old version with all chunks deleted and re-created

### Implementation for User Story 2

- [ ] T029 [US2] Implement duplicate detection in src/ingestion/chroma_client.py: datasheet_exists() using metadata filtering on datasheet_name
- [ ] T030 [US2] Implement chunk deletion in src/ingestion/chroma_client.py: delete_datasheet() to remove all chunks for a specific datasheet by metadata filter
- [ ] T031 [US2] Verify --force-update flag is already added in T024 (no additional work needed here)
- [ ] T032 [US2] Integrate duplicate check in src/ingestion/pipeline.py: check before ingestion, skip if exists and not force-update
- [ ] T033 [US2] Implement force-update logic in src/ingestion/pipeline.py: delete existing chunks before re-ingestion when flag is set
- [ ] T034 [US2] Add skip logging in src/ingestion/pipeline.py: log "Already exists, skipping" with datasheet name and skip reason
- [ ] T035 [US2] Update batch summary in src/models/datasheet.py: include skipped count and list skipped datasheets in report
- [ ] T036 [US2] Add force-update indicator to console banner in src/cli/ingest.py (show "Force Update: Yes/No")

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - engineers can ingest new datasheets (US1) and update existing ones with --force-update (US2) independently

---

## Phase 5: User Story 3 - Error Handling and Validation (Priority: P3)

**Goal**: Provide clear feedback on data quality issues (corrupted markdown, missing images, malformed tables) with partial success handling and actionable error messages

**Independent Test**: Provide intentionally problematic datasheets (missing .md file, corrupt markdown, missing images) and verify appropriate error messages are logged with clear actions while other datasheets continue processing

### Implementation for User Story 3

- [ ] T037 [P] [US3] Add markdown file validation in src/ingestion/markdown_parser.py: handle UnicodeDecodeError, empty files, malformed syntax with graceful error recovery
- [ ] T038 [P] [US3] Add image path validation in src/ingestion/markdown_parser.py: check if image files exist, log warnings for missing images but continue ingestion
- [ ] T039 [US3] Add folder validation in src/utils/validators.py: check for exactly one .md file per folder, readable permissions, valid folder names
- [ ] T040 [US3] Implement error message formatting in src/utils/logger.py: structured format with datasheet name, error summary, file path, reason, and suggested action
- [ ] T041 [US3] Add ChromaDB connection validation in src/ingestion/chroma_client.py: check path accessibility, permissions, and collection creation with clear error messages
- [ ] T042 [US3] Add per-datasheet error handling in src/ingestion/pipeline.py: catch exceptions, log errors, continue processing remaining datasheets
- [ ] T043 [US3] Add batch-level error handling in src/ingestion/pipeline.py: detect ChromaDB connection failures, invalid folder paths, and abort with appropriate exit codes
- [ ] T044 [US3] Update batch summary in src/models/datasheet.py: include failed count and detailed error messages in summary report
- [ ] T045 [US3] Add large chunk warnings in src/ingestion/chunker.py: log warning when chunk exceeds 1500 chars (target) but under 2000 (limit) due to large tables
- [ ] T046 [US3] Add validation for special characters in src/utils/validators.py: check folder names for Windows-reserved characters and log warnings

**Checkpoint**: All user stories should now be independently functional - engineers can ingest datasheets (US1), update them (US2), and get clear error feedback for issues (US3)

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final documentation

- [ ] T047 [P] Update README.md with project overview, setup instructions, and basic usage examples
- [ ] T048 [P] Update pyproject.toml with pinned versions and installation notes for PyTorch CPU-only
- [ ] T049 [P] Create .gitignore for Python project: include .logs/, __pycache__/, venv/, .pytest_cache/, *.pyc
- [ ] T050 [P] Add docstrings to all public functions and classes following Numpy Style Guide
- [ ] T051 [P] Add type hints to all function signatures using Python 3.10+ syntax
- [ ] T052 Validate quickstart.md examples: run all CLI commands in quickstart guide to verify accuracy
- [ ] T053 Add performance metrics logging: track average ingestion time, chunks per second, throughput in batch summary
- [ ] T054 Add collection metadata verification in src/ingestion/chroma_client.py: log collection info (count, schema version) at startup
- [ ] T055 [P] Create sample datasheet fixtures in tests/fixtures/sample_datasheets/ for validation testing
- [ ] T056 Code cleanup: remove debug print statements, ensure consistent error handling patterns across all modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion (T001-T007) - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion (T008-T015)
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (US1 → US2 → US3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1 but integrates with ingest_datasheet()
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent of US1/US2 but adds error handling throughout pipeline

### Within Each User Story

- **US1**: Markdown parser and image resolution (T016-T017) → Chunker (T018-T019) → ChromaDB operations (T020) → Pipeline orchestration (T021-T023) → CLI (T024-T028)
- **US2**: ChromaDB duplicate detection and deletion (T029-T030) → CLI flag (T031) → Pipeline integration (T032-T035) → UI updates (T036)
- **US3**: Validation and error handling across all components (T037-T046), can be worked on in parallel for different modules

### Parallel Opportunities

**Setup Phase (Phase 1)**:
- T005, T006, T007 can run in parallel (different directories)

**Foundational Phase (Phase 2)**:
- T008, T009, T010 can run in parallel (different modules)
- T011, T012, T013, T014 can run in parallel (different model classes)

**User Story 1 (Phase 3)**:
- T016 and T017 can run in parallel (different functions in same file, no conflicts)
- Once Foundational is complete, US1, US2, US3 can start in parallel by different developers

**User Story 3 (Phase 5)**:
- T037, T038, T039, T040, T041 can run in parallel (different modules)

**Polish Phase (Phase 6)**:
- T047, T048, T049, T050, T051, T055 can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# Launch foundational models together (Phase 2):
Task: "Create Datasheet model in src/models/datasheet.py"
Task: "Create ContentChunk model in src/models/chunk.py"
Task: "Create IngestionResult model in src/models/datasheet.py"
Task: "Create BatchIngestionReport model in src/models/datasheet.py"

# Launch US1 parsers together (Phase 3):
Task: "Implement markdown parser in src/ingestion/markdown_parser.py"
Task: "Implement image path resolution in src/ingestion/markdown_parser.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007) → ~30 minutes
2. Complete Phase 2: Foundational (T008-T015) → ~4-6 hours (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (T016-T028) → ~8-10 hours
4. **STOP and VALIDATE**: Test User Story 1 independently with sample datasheets
5. Deploy/demo: Engineers can now ingest datasheets into ChromaDB

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 (User Story 1) = ~13-17 hours total

### Incremental Delivery

1. **Foundation** (Phase 1 + 2): Setup + Foundational → Foundation ready
2. **MVP** (Phase 3): Add User Story 1 → Test with sample datasheets → **First deployable version!**
3. **Enhancement 1** (Phase 4): Add User Story 2 → Test update workflows → Deploy/Demo
4. **Enhancement 2** (Phase 5): Add User Story 3 → Test error scenarios → Deploy/Demo
5. **Polish** (Phase 6): Documentation and refinement → Production-ready

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (critical path)
2. **Once Foundational is done (T015 complete)**:
   - Developer A: User Story 1 (T016-T028) - Core ingestion
   - Developer B: User Story 2 (T029-T036) - Update logic
   - Developer C: User Story 3 (T037-T046) - Error handling
3. Stories complete and integrate independently
4. Team reconvenes for Phase 6 polish

---

## Success Criteria Validation

### After US1 Completion:

- [ ] Can ingest a 20-page datasheet in < 30 seconds (SC-002)
- [ ] Tables and code blocks remain intact in single chunks (SC-003)
- [ ] Image paths converted to absolute paths successfully (SC-004)
- [ ] Chunks stored in ChromaDB with proper metadata (datasheet_name, folder_path, chunk_index)

### After US2 Completion:

- [ ] Duplicate detection works with 100% accuracy (SC-005)
- [ ] Force-update replaces existing datasheets completely (SC-008)
- [ ] Skipped datasheets logged correctly

### After US3 Completion:

- [ ] 95%+ of well-formed datasheets ingest without errors (SC-001)
- [ ] Clear error messages for all failure modes (SC-007)
- [ ] Partial batch success: one failed datasheet doesn't stop others

### After Polish (Phase 6):

- [ ] All quickstart.md examples work correctly
- [ ] README.md setup instructions accurate
- [ ] Code follows Python style guide with type hints and docstrings

---

## Notes

- [P] tasks = different files or different functions with no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Windows-specific paths**: Use pathlib.Path for cross-platform compatibility where possible
- **Performance targets**: Log warnings when exceeded but continue processing
- **Tests**: Not included in this task list as they were not requested in the specification

---

## Task Count Summary

- **Phase 1 (Setup)**: 7 tasks
- **Phase 2 (Foundational)**: 8 tasks (CRITICAL PATH)
- **Phase 3 (US1 - MVP)**: 13 tasks
- **Phase 4 (US2)**: 8 tasks
- **Phase 5 (US3)**: 10 tasks
- **Phase 6 (Polish)**: 10 tasks

**Total Tasks**: 56 tasks

**Parallel Opportunities**: 15 tasks marked with [P] can run in parallel within their phase
**Estimated MVP Time**: ~13-17 hours (Phase 1 + 2 + 3)
**Estimated Full Implementation**: ~30-40 hours (all phases)

---

## Suggested MVP Scope

For the minimal viable product that delivers immediate value:

**Include**:
- Phase 1: Setup (T001-T007)
- Phase 2: Foundational (T008-T015)
- Phase 3: User Story 1 (T016-T028)
- Selected Polish tasks: T047 (README), T048 (requirements.txt), T052 (validate quickstart)

**Defer to later iterations**:
- Phase 4: User Story 2 (engineers can manually delete and re-run for updates initially)
- Phase 5: User Story 3 (basic error handling in US1 is sufficient for MVP)
- Remaining Polish tasks

This MVP delivers the core value: **engineers can ingest datasheets into ChromaDB for AI-assisted queries**.
