# CLI Interface Contract

**Feature**: 001-datasheet-ingestion-pipeline  
**Date**: 2025-01-22  
**Version**: 1.0.0

## Overview

This document defines the command-line interface contract for the datasheet ingestion pipeline. The CLI provides a single command for ingesting markdown datasheets into ChromaDB with optional force-update behavior.

---

## Command Specification

### Basic Usage

```bash
python -m src.cli.ingest <datasheets_folder_path> [--force-update] [--log-level LEVEL]
```

### Entry Point

**Module**: `src.cli.ingest`  
**Function**: `main()`  
**Exit Codes**:
- `0`: Success (all datasheets processed successfully or skipped)
- `1`: Validation error (invalid arguments or folder structure)
- `2`: ChromaDB connection error
- `3`: Ingestion error (one or more datasheets failed)

---

## Arguments

### Positional Arguments

#### `datasheets_folder_path`

**Type**: `Path` (string converted to pathlib.Path)  
**Required**: Yes  
**Description**: Absolute or relative path to folder containing datasheet subfolders

**Validation**:
- Path must exist
- Path must be a directory
- Path must be readable

**Example Values**:
```bash
D:\datasheets
D:\projects\pcb\components
.\datasheets
..\shared\datasheets
```

**Expected Folder Structure**:
```
datasheets_folder_path/
├── TL072/
│   ├── TL072.md
│   └── images/
│       └── pinout.png
├── LM358/
│   ├── LM358.md
│   └── images/
│       └── schematic.png
└── ATmega328P/
    └── ATmega328P.md
```

**Error Messages**:

```bash
# Path doesn't exist
ERROR: Folder does not exist: D:\datasheets\nonexistent
  Action: Verify the path and try again

# Path is not a directory
ERROR: Path is not a directory: D:\datasheets\file.txt
  Action: Provide a folder path, not a file path

# Permission denied
ERROR: Cannot read folder: D:\restricted\datasheets
  Action: Check folder permissions and try again
```

---

### Optional Flags

#### `--force-update`

**Type**: Boolean flag (store_true)  
**Required**: No  
**Default**: `False`  
**Description**: Re-ingest datasheets that already exist in ChromaDB. Deletes old chunks before re-ingesting.

**Behavior**:

| Scenario | `--force-update` absent | `--force-update` present |
|----------|------------------------|--------------------------|
| Datasheet exists in ChromaDB | Skip (log message) | Delete old chunks, re-ingest |
| Datasheet is new | Ingest normally | Ingest normally |

**Example Usage**:
```bash
# Initial ingestion (new datasheets only)
python -m src.cli.ingest D:\datasheets

# Force re-ingestion of all datasheets
python -m src.cli.ingest D:\datasheets --force-update
```

**Output Messages**:
```bash
# Without --force-update
INFO [TL072]: Already exists in ChromaDB, skipping (use --force-update to re-ingest)

# With --force-update
INFO [TL072]: Deleting 12 existing chunks
INFO [TL072]: Re-ingesting datasheet
```

---

#### `--log-level`

**Type**: Choice (one of: DEBUG, INFO, WARNING, ERROR)  
**Required**: No  
**Default**: `INFO`  
**Description**: Set logging verbosity level

**Levels**:
- `DEBUG`: All messages including parsing details, chunk content previews
- `INFO`: Progress messages, success/skip/error status per datasheet
- `WARNING`: Warnings (missing images, slow ingestion) and errors
- `ERROR`: Only error messages

**Example Usage**:
```bash
# Default (INFO level)
python -m src.cli.ingest D:\datasheets

# Verbose debugging
python -m src.cli.ingest D:\datasheets --log-level DEBUG

# Quiet mode (errors only)
python -m src.cli.ingest D:\datasheets --log-level ERROR
```

**Output Samples**:

```bash
# DEBUG level
DEBUG [TL072]: Found markdown file: D:\datasheets\TL072\TL072.md
DEBUG [TL072]: Parsing markdown content (3245 characters)
DEBUG [TL072]: Stage 1 splitting: 4 markdown groups
DEBUG [TL072]: Stage 2 splitting: 12 final chunks
DEBUG [TL072]: Chunk 0 preview: "# TL072 Dual JFET-Input..."
DEBUG [TL072]: Generating embeddings for 12 chunks
DEBUG [TL072]: Inserting chunks into ChromaDB

# INFO level (default)
INFO [TL072]: Processing datasheet
INFO [TL072]: Created 12 chunks (duration: 4.2s)
INFO [TL072]: ✅ Success

# WARNING level
WARNING [LM358]: Image not found: D:\datasheets\LM358\images\missing.png
WARNING [ATmega328P]: Ingestion exceeded 30-second target (actual: 35.2s)

# ERROR level
ERROR [NE555]: Failed to parse markdown file
  File: D:\datasheets\NE555\NE555.md
  Reason: UnicodeDecodeError: invalid continuation byte
  Action: Check file encoding (expected UTF-8)
```

---

## Help Text

**Command**: `python -m src.cli.ingest --help`

**Output**:
```
usage: ingest [-h] [--force-update] [--log-level {DEBUG,INFO,WARNING,ERROR}]
              datasheets_folder_path

Ingest electrical component datasheets into ChromaDB

positional arguments:
  datasheets_folder_path
                        Path to folder containing datasheet subfolders

options:
  -h, --help            show this help message and exit
  --force-update        Re-ingest datasheets that already exist in ChromaDB
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Logging verbosity level (default: INFO)

Examples:
  python -m src.cli.ingest D:\datasheets
  python -m src.cli.ingest D:\datasheets --force-update
```

---

## Output Format

### Standard Output (Console)

#### Success Case

```
=================================================================
Datasheet Ingestion Pipeline
=================================================================
Folder: D:\datasheets
ChromaDB: D:\.cache\chromadb (collection: datasheets)
Force Update: No
=================================================================

INFO [TL072]: Processing datasheet
INFO [TL072]: Created 12 chunks (duration: 4.2s)
INFO [TL072]: ✅ Success

INFO [LM358]: Already exists in ChromaDB, skipping
INFO [LM358]: ⏭️  Skipped

INFO [ATmega328P]: Processing datasheet
INFO [ATmega328P]: Created 45 chunks (duration: 18.3s)
INFO [ATmega328P]: ✅ Success

=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 3
  ✅ Successful: 2
  ⏭️  Skipped: 1
  ❌ Failed: 0

Total Chunks Created: 57
Total Duration: 22.5 seconds
Success Rate: 100.0%
=================================================================
```

#### Error Case

```
=================================================================
Datasheet Ingestion Pipeline
=================================================================
Folder: D:\datasheets
ChromaDB: D:\.cache\chromadb (collection: datasheets)
Force Update: No
=================================================================

INFO [TL072]: Processing datasheet
INFO [TL072]: Created 12 chunks (duration: 4.2s)
INFO [TL072]: ✅ Success

ERROR [NE555]: Failed to parse markdown file
  File: D:\datasheets\NE555\NE555.md
  Reason: UnicodeDecodeError: invalid continuation byte
  Action: Check file encoding (expected UTF-8)
INFO [NE555]: ❌ Error

INFO [LM358]: Processing datasheet
INFO [LM358]: Created 8 chunks (duration: 3.1s)
INFO [LM358]: ✅ Success

=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 3
  ✅ Successful: 2
  ⏭️  Skipped: 0
  ❌ Failed: 1

Total Chunks Created: 20
Total Duration: 7.3 seconds
Success Rate: 66.7%

❌ Failed Datasheets:
  - NE555: UnicodeDecodeError: invalid continuation byte
=================================================================

Exit Code: 3 (ingestion error)
```

#### Warning Case (Performance)

```
=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 5
  ✅ Successful: 5
  ⏭️  Skipped: 0
  ❌ Failed: 0

Total Chunks Created: 234
Total Duration: 156.8 seconds
Success Rate: 100.0%

⚠️  Slow Ingestions (>30s): 2
  - ATmega2560 (45.2s)
  - STM32F407 (38.7s)
=================================================================
```

---

### JSON Log File (Structured Logging)

**Location**: `.logs/ingestion_YYYYMMDD_HHMMSS.json`  
**Format**: One JSON object per line (JSONL)

**Example Log Entries**:

```json
{"timestamp":"2025-01-22T10:30:00Z","level":"INFO","datasheet":"TL072","message":"Processing datasheet","folder_path":"D:\\datasheets\\TL072"}
{"timestamp":"2025-01-22T10:30:02Z","level":"DEBUG","datasheet":"TL072","message":"Parsing markdown content","file_size_bytes":3245}
{"timestamp":"2025-01-22T10:30:03Z","level":"DEBUG","datasheet":"TL072","message":"Semantic chunking complete","chunk_count":12}
{"timestamp":"2025-01-22T10:30:04Z","level":"INFO","datasheet":"TL072","message":"Ingestion successful","chunk_count":12,"duration_ms":4200}
{"timestamp":"2025-01-22T10:30:05Z","level":"WARNING","datasheet":"LM358","message":"Image not found","expected_path":"D:\\datasheets\\LM358\\images\\missing.png"}
{"timestamp":"2025-01-22T10:30:06Z","level":"ERROR","datasheet":"NE555","message":"Failed to parse markdown","error":"UnicodeDecodeError: invalid continuation byte"}
```

**JSON Schema**:

```json
{
  "timestamp": "string (ISO 8601)",
  "level": "string (DEBUG|INFO|WARNING|ERROR)",
  "datasheet": "string (folder name)",
  "message": "string (human-readable message)",
  "folder_path": "string (optional, absolute path)",
  "file_size_bytes": "integer (optional)",
  "chunk_count": "integer (optional)",
  "duration_ms": "integer (optional)",
  "error": "string (optional, exception message)"
}
```

---

## Environment Variables

### `CHROMADB_PATH`

**Type**: String (path)  
**Required**: No  
**Default**: `D:\.cache\chromadb`  
**Description**: Override default ChromaDB storage location

**Example**:
```bash
# Windows (PowerShell)
$env:CHROMADB_PATH = "E:\vectordb\chromadb"
python -m src.cli.ingest D:\datasheets

# Windows (CMD)
set CHROMADB_PATH=E:\vectordb\chromadb
python -m src.cli.ingest D:\datasheets
```

### `CHROMADB_COLLECTION`

**Type**: String  
**Required**: No  
**Default**: `datasheets`  
**Description**: Override default ChromaDB collection name

**Example**:
```bash
$env:CHROMADB_COLLECTION = "my_datasheets"
python -m src.cli.ingest D:\datasheets
```

---

## Exit Codes

| Code | Constant | Meaning | Example Cause |
|------|----------|---------|---------------|
| 0 | `EXIT_SUCCESS` | All datasheets processed successfully or skipped | Normal operation |
| 1 | `EXIT_VALIDATION_ERROR` | Invalid arguments or folder structure | Folder doesn't exist, invalid path |
| 2 | `EXIT_CHROMADB_ERROR` | ChromaDB connection or initialization failed | ChromaDB path inaccessible, permission denied |
| 3 | `EXIT_INGESTION_ERROR` | One or more datasheets failed to ingest | Parse error, encoding error, chunk generation failure |

**Exit Code Logic**:

```python
# Success: All datasheets either succeeded or skipped
if batch_report.failed == 0:
    return EXIT_SUCCESS

# ChromaDB error: Cannot connect or initialize
except chromadb.errors.ChromaError:
    return EXIT_CHROMADB_ERROR

# Validation error: Invalid arguments
except (FileNotFoundError, NotADirectoryError):
    return EXIT_VALIDATION_ERROR

# Ingestion error: One or more datasheets failed
if batch_report.failed > 0:
    return EXIT_INGESTION_ERROR
```

---

## Integration Examples

### PowerShell Script

```powershell
# ingest-all.ps1
$DatasheetFolder = "D:\datasheets"
$LogFile = "ingestion-report.txt"

Write-Host "Starting datasheet ingestion..."

python -m src.cli.ingest $DatasheetFolder --log-level INFO | Tee-Object -FilePath $LogFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Ingestion completed successfully" -ForegroundColor Green
} elseif ($LASTEXITCODE -eq 3) {
    Write-Host "⚠️  Ingestion completed with errors (see $LogFile)" -ForegroundColor Yellow
} else {
    Write-Host "❌ Ingestion failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
}

exit $LASTEXITCODE
```

### Batch Script (Windows CMD)

```batch
@echo off
REM ingest-all.bat

set DATASHEET_FOLDER=D:\datasheets

echo Starting datasheet ingestion...
python -m src.cli.ingest %DATASHEET_FOLDER% --log-level INFO

if %ERRORLEVEL% EQU 0 (
    echo Ingestion completed successfully
) else if %ERRORLEVEL% EQU 3 (
    echo Ingestion completed with errors
) else (
    echo Ingestion failed with exit code %ERRORLEVEL%
)

exit /b %ERRORLEVEL%
```

### Python Integration

```python
import subprocess
import sys
from pathlib import Path

def ingest_datasheets(folder: Path, force_update: bool = False) -> int:
    """
    Programmatically invoke ingestion CLI.
    
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    cmd = [
        sys.executable,
        "-m",
        "src.cli.ingest",
        str(folder)
    ]
    
    if force_update:
        cmd.append("--force-update")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode

# Usage
exit_code = ingest_datasheets(Path("D:/datasheets"), force_update=True)
sys.exit(exit_code)
```

---

## Error Handling Contract

### Error Message Format

**Template**:
```
ERROR [<datasheet_name>]: <error_summary>
  <Detail Field 1>: <value>
  <Detail Field 2>: <value>
  Action: <suggested fix>
```

**Examples**:

```
ERROR [TL072]: Failed to parse markdown file
  File: D:\datasheets\TL072\TL072.md
  Reason: Malformed table at line 45
  Action: Check markdown syntax or skip this datasheet

ERROR [LM358]: No markdown file found in folder
  Folder: D:\datasheets\LM358
  Files Found: image1.png, image2.png
  Action: Add a .md file to this folder

ERROR [ATmega328P]: ChromaDB insertion failed
  Reason: Duplicate ID collision
  Chunks Affected: 3/45
  Action: Re-run with --force-update to clear existing chunks

ERROR [GLOBAL]: ChromaDB connection failed
  Path: D:\.cache\chromadb
  Reason: Permission denied
  Action: Check folder permissions or set CHROMADB_PATH environment variable
```

### Warning Message Format

**Template**:
```
WARNING [<datasheet_name>]: <warning_summary>
  <Context>: <value>
  <Impact>: <what happens>
```

**Examples**:

```
WARNING [LM358]: Image not found
  Expected: D:\datasheets\LM358\images\pinout.png
  Referenced in: D:\datasheets\LM358\LM358.md:23
  Impact: Image path not included in chunk metadata

WARNING [ATmega328P]: Ingestion exceeded 30-second target
  Actual Duration: 35.2 seconds
  Chunks Created: 87
  Impact: None (target is a guideline, not a hard limit)

WARNING [TL072]: Large chunk detected
  Chunk Index: 7
  Size: 1823 characters (target: 1500)
  Impact: Chunk stored as-is (contains large table that cannot be split)
```

---

## Version Compatibility

### Python Version

**Required**: Python 3.10+  
**Tested**: Python 3.13

**Version Check**:
```python
import sys

if sys.version_info < (3, 10):
    print("ERROR: Python 3.10 or higher required")
    sys.exit(1)
```

### ChromaDB Version

**Required**: ChromaDB 0.4.22+  
**Recommended**: Latest stable release

**Compatibility Check** (future):
```python
import chromadb

if chromadb.__version__ < "0.4.22":
    print(f"WARNING: ChromaDB {chromadb.__version__} detected (0.4.22+ recommended)")
```

---

## Security Considerations

### Path Traversal Prevention

**Risk**: User provides malicious path like `../../../../etc/passwd`  
**Mitigation**: All paths resolved to absolute paths with validation

```python
def validate_folder_path(path: Path) -> Path:
    """Resolve and validate folder path, preventing traversal attacks."""
    resolved = path.resolve()
    
    # Ensure path is within allowed base directories
    # (Future: implement allowlist if needed)
    
    if not resolved.exists():
        raise FileNotFoundError(f"Folder does not exist: {resolved}")
    
    if not resolved.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {resolved}")
    
    return resolved
```

### Injection Prevention

**Risk**: Folder names with special characters causing command injection  
**Mitigation**: Use pathlib and argparse (no shell=True subprocess calls)

**Safe Operations**:
- ✅ `Path(user_input).resolve()` - Safe path handling
- ✅ `argparse.ArgumentParser()` - Validated arguments
- ❌ `os.system(f"process {user_input}")` - Vulnerable (not used)

---

## Performance Guarantees

| Operation | Target | Guarantee |
|-----------|--------|-----------|
| CLI startup | < 2s | Soft target (Python import overhead) |
| Folder validation | < 1s | Hard limit (filesystem check) |
| Single datasheet | < 30s | Soft target (warning if exceeded) |
| 100 datasheets | < 30 min | Soft target (warning if exceeded) |
| Error reporting | Immediate | Hard limit (synchronous logging) |

**Soft Target**: Performance goal; warning logged if exceeded, but operation continues  
**Hard Limit**: Operation fails or times out if exceeded

---

## Future Enhancements (Not in v1.0)

- ✨ `--dry-run` flag: Preview ingestion without writing to ChromaDB
- ✨ `--filter PATTERN` flag: Only ingest datasheets matching glob pattern
- ✨ `--validate-only` flag: Check folder structure without ingesting
- ✨ `--config FILE` flag: Load settings from YAML/JSON config file
- ✨ `--parallel N` flag: Process N datasheets in parallel (requires thread-safe ChromaDB client)
- ✨ Progress bar: Display real-time progress during batch ingestion
- ✨ JSON output mode: `--output-format json` for machine-readable results

---

## Summary

**CLI Contract Version**: 1.0.0  
**Entry Point**: `python -m src.cli.ingest`  
**Required Arguments**: `datasheets_folder_path`  
**Optional Flags**: `--force-update`, `--log-level`  
**Exit Codes**: 0 (success), 1 (validation), 2 (ChromaDB), 3 (ingestion)  
**Output**: Console (human-readable) + JSON logs (structured)  

**Status**: Ready for implementation
