# Quickstart Guide: Datasheet Ingestion Pipeline

**Feature**: 001-datasheet-ingestion-pipeline  
**Date**: 2025-01-22  
**Version**: 1.0.0

## Overview

This guide provides practical examples and common workflows for using the datasheet ingestion pipeline. Follow these steps to get started quickly.

---

## Prerequisites

### System Requirements

- **Operating System**: Windows 10/11 (primary), Linux/macOS (untested but should work)
- **Python**: 3.10 or higher (tested with Python 3.13)
- **Disk Space**: Minimum 2 GB for ChromaDB storage (depends on datasheet count)
- **RAM**: Minimum 4 GB (8 GB recommended for large batches)

### Required Setup

1. **Python Installation**: Verify Python version
   ```bash
   python --version
   # Expected: Python 3.10.x or higher
   ```

2. **Install uv** (modern Python package manager):
   ```bash
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Linux/macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Verify installation
   uv --version
   ```

3. **Git Clone** (if not already done):
   ```bash
   git clone https://github.com/your-org/pdf-knowledgebase.git
   cd pdf-knowledgebase
   ```

4. **Install Dependencies with uv**:
   ```bash
   # uv automatically creates and manages the virtual environment
   # Install CPU-only PyTorch first (avoid CUDA dependencies)
   uv pip install torch --index-url https://download.pytorch.org/whl/cpu
   
   # Install remaining dependencies from pyproject.toml
   uv sync
   ```

5. **Verify Installation**:
   ```bash
   uv run python -c "import chromadb; print(f'ChromaDB {chromadb.__version__} installed')"
   uv run python -c "import langchain; print(f'LangChain {langchain.__version__} installed')"
   ```

---

## Quick Start: First Ingestion

### Step 1: Prepare Datasheet Folder

Create a folder structure with your datasheets:

```
D:\datasheets\
├── TL072\
│   ├── TL072.md          # Required: One markdown file
│   └── images\
│       └── pinout.png    # Optional: Images
├── LM358\
│   └── LM358.md
└── NE555\
    ├── NE555.md
    └── images\
        ├── schematic.png
        └── timing_diagram.png
```

**Important**: Each datasheet must be in its own subfolder with exactly one `.md` file.

### Step 2: Run First Ingestion

```bash
# Navigate to project root
cd D:\Python\Projects\pdf-knowledgebase

# Run ingestion with uv
uv run python -m src.cli.ingest D:\datasheets
```

**Expected Output**:
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

INFO [LM358]: Processing datasheet
INFO [LM358]: Created 8 chunks (duration: 3.1s)
INFO [LM358]: ✅ Success

INFO [NE555]: Processing datasheet
INFO [NE555]: Created 15 chunks (duration: 5.8s)
INFO [NE555]: ✅ Success

=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 3
  ✅ Successful: 3
  ⏭️  Skipped: 0
  ❌ Failed: 0

Total Chunks Created: 35
Total Duration: 13.1 seconds
Success Rate: 100.0%
=================================================================
```

### Step 3: Verify Ingestion

Check that ChromaDB collection was created:

```python
# verify-ingestion.py
import chromadb

client = chromadb.PersistentClient(path=r"D:\.cache\chromadb")
collection = client.get_collection("datasheets")

# Get collection info
print(f"Total chunks: {collection.count()}")

# Get unique datasheets
results = collection.get(include=["metadatas"])
datasheets = set(meta['datasheet_name'] for meta in results['metadatas'])
print(f"Datasheets ingested: {sorted(datasheets)}")
```

**Expected Output**:
```
Total chunks: 35
Datasheets ingested: ['LM358', 'NE555', 'TL072']
```

---

## Common Workflows

### Workflow 1: Adding New Datasheets

**Scenario**: You've added new datasheets to your folder and want to ingest only the new ones.

```bash
# Add new datasheets to folder
D:\datasheets\
├── TL072\           # Already ingested
├── LM358\           # Already ingested
├── NE555\           # Already ingested
└── ATmega328P\      # New datasheet
    └── ATmega328P.md

# Run ingestion (existing datasheets will be skipped)
uv run python -m src.cli.ingest D:\datasheets
```

**Output**:
```
INFO [TL072]: Already exists in ChromaDB, skipping
INFO [TL072]: ⏭️  Skipped

INFO [LM358]: Already exists in ChromaDB, skipping
INFO [LM358]: ⏭️  Skipped

INFO [NE555]: Already exists in ChromaDB, skipping
INFO [NE555]: ⏭️  Skipped

INFO [ATmega328P]: Processing datasheet
INFO [ATmega328P]: Created 45 chunks (duration: 18.3s)
INFO [ATmega328P]: ✅ Success

=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 4
  ✅ Successful: 1
  ⏭️  Skipped: 3
  ❌ Failed: 0

Total Chunks Created: 45
Total Duration: 18.3 seconds
Success Rate: 100.0%
=================================================================
```

---

### Workflow 2: Updating Existing Datasheets

**Scenario**: You've updated a datasheet markdown file and want to re-ingest it.

```bash
# Edit the datasheet
# Example: D:\datasheets\TL072\TL072.md (add new section)

# Re-ingest with --force-update flag
uv run python -m src.cli.ingest D:\datasheets --force-update
```

**Output**:
```
INFO [TL072]: Deleting 12 existing chunks
INFO [TL072]: Re-ingesting datasheet
INFO [TL072]: Created 14 chunks (duration: 4.5s)
INFO [TL072]: ✅ Success

INFO [LM358]: Deleting 8 existing chunks
INFO [LM358]: Re-ingesting datasheet
INFO [LM358]: Created 8 chunks (duration: 3.2s)
INFO [LM358]: ✅ Success

...
```

**Tip**: Use `--force-update` sparingly, as it deletes and re-ingests all datasheets, which is slower than ingesting only new ones.

---

### Workflow 3: Troubleshooting Failed Ingestions

**Scenario**: Some datasheets failed to ingest, and you need to debug the issue.

```bash
# Run with DEBUG log level for detailed output
uv run python -m src.cli.ingest D:\datasheets --log-level DEBUG
```

**Output**:
```
DEBUG [TL072]: Found markdown file: D:\datasheets\TL072\TL072.md
DEBUG [TL072]: Parsing markdown content (3245 characters)
DEBUG [TL072]: Stage 1 splitting: 4 markdown groups
DEBUG [TL072]: Stage 2 splitting: 12 final chunks
DEBUG [TL072]: Chunk 0 preview: "# TL072 Dual JFET-Input..."
DEBUG [TL072]: Generating embeddings for 12 chunks
DEBUG [TL072]: Inserting chunks into ChromaDB
INFO [TL072]: ✅ Success

ERROR [NE555]: Failed to parse markdown file
  File: D:\datasheets\NE555\NE555.md
  Reason: UnicodeDecodeError: invalid continuation byte at position 123
  Action: Check file encoding (expected UTF-8)

DEBUG [NE555]: Stack trace:
  File "src/ingestion/markdown_parser.py", line 45, in parse_markdown
    content = file.read()
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 123
```

**Common Issues and Fixes**:

| Error | Cause | Solution |
|-------|-------|----------|
| `UnicodeDecodeError` | Non-UTF-8 encoding | Convert markdown to UTF-8 encoding |
| `FileNotFoundError: No markdown file found` | Missing `.md` file | Add a markdown file to the folder |
| `ValueError: Multiple markdown files found` | Multiple `.md` files | Keep only one `.md` file per folder |
| `ChromaDB connection failed` | ChromaDB path inaccessible | Check `CHROMADB_PATH` or folder permissions |
| Image not found warning | Broken image link | Update image path in markdown or ignore warning |

---

### Workflow 4: Batch Ingestion of Large Collections

**Scenario**: Ingesting 100+ datasheets and monitoring progress.

```bash
# Run with INFO level (default) to see progress
uv run python -m src.cli.ingest D:\large_datasheet_collection
```

**Expected Behavior**:
- Each datasheet logs progress: "Processing", "Created N chunks", "Success/Error/Skipped"
- Warnings logged for slow ingestions (>30 seconds per datasheet)
- Summary report at the end

**Performance Tips**:
1. **Close unnecessary applications** to free up RAM
2. **Use SSD storage** for ChromaDB path (faster disk I/O)
3. **Process smaller batches** if system struggles (split into 50-datasheet chunks)
4. **Check log file** for detailed timing: `.logs/ingestion_YYYYMMDD_HHMMSS.json`

**Example Summary for Large Batch**:
```
=================================================================
Ingestion Batch Summary
=================================================================
Total Datasheets: 120
  ✅ Successful: 115
  ⏭️  Skipped: 3
  ❌ Failed: 2

Total Chunks Created: 3,847
Total Duration: 1,245.3 seconds (20.8 minutes)
Success Rate: 95.8%

⚠️  Slow Ingestions (>30s): 8
  - STM32F407 (45.2s)
  - ATmega2560 (38.7s)
  - PIC18F4550 (35.1s)
  - MSP430F5529 (33.4s)
  - ESP32_S3 (32.8s)
  ... and 3 more

❌ Failed Datasheets:
  - BCM2837: UnicodeDecodeError: invalid continuation byte
  - FPGA_XC7A35T: No markdown file found in folder
=================================================================
```

---

### Workflow 5: Custom ChromaDB Location

**Scenario**: You want to use a different ChromaDB storage location (e.g., external drive).

```bash
# Windows (PowerShell)
$env:CHROMADB_PATH = "E:\vectordb\chromadb"
uv run python -m src.cli.ingest D:\datasheets

# Windows (CMD)
set CHROMADB_PATH=E:\vectordb\chromadb
uv run python -m src.cli.ingest D:\datasheets

# Linux/macOS
export CHROMADB_PATH="/mnt/external/chromadb"
uv run python -m src.cli.ingest ~/datasheets
```

**Verification**:
```
INFO: Using ChromaDB path: E:\vectordb\chromadb
INFO: Collection: datasheets
```

---

## Usage Examples

### Example 1: Single Datasheet Folder

```bash
# Folder structure
D:\projects\pcb\opamps\TL072\
├── TL072.md
└── images\
    └── pinout.png

# Ingest single datasheet
uv run python -m src.cli.ingest D:\projects\pcb\opamps\TL072
```

**Note**: The CLI expects a folder containing datasheet subfolders. For a single datasheet, ensure the path points to the parent folder containing the datasheet folder.

**Correct**:
```
D:\projects\pcb\opamps\      # Pass this path to CLI
└── TL072\
    └── TL072.md
```

**Incorrect**:
```
D:\projects\pcb\opamps\TL072\   # Don't pass datasheet folder directly
└── TL072.md
```

---

### Example 2: Incremental Daily Updates

**Scenario**: You add datasheets daily and want to ingest only new ones.

```bash
# daily-ingest.ps1 (PowerShell script)
$DatasheetFolder = "D:\datasheets"
$LogFile = "ingestion-$(Get-Date -Format 'yyyyMMdd').txt"

Write-Host "=== Daily Datasheet Ingestion ===" -ForegroundColor Cyan
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Folder: $DatasheetFolder"
Write-Host ""

# Run ingestion (without --force-update to skip existing)
uv run python -m src.cli.ingest $DatasheetFolder --log-level INFO | Tee-Object -FilePath $LogFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Ingestion completed successfully" -ForegroundColor Green
} else {
    Write-Host "`n❌ Ingestion failed (see $LogFile)" -ForegroundColor Red
}
```

**Schedule with Task Scheduler** (Windows):
1. Open Task Scheduler
2. Create Basic Task: "Daily Datasheet Ingestion"
3. Trigger: Daily at 2:00 AM
4. Action: Start a program → `powershell.exe -File C:\scripts\daily-ingest.ps1`

---

### Example 3: Validating Folder Structure Before Ingestion

**Scenario**: Check if datasheet folders are correctly structured before running ingestion.

```python
# validate-structure.py
from pathlib import Path
import sys

def validate_datasheet_folder(folder: Path) -> list[str]:
    """Validate datasheet folder structure and return issues."""
    issues = []
    
    if not folder.exists():
        issues.append(f"Folder does not exist: {folder}")
        return issues
    
    if not folder.is_dir():
        issues.append(f"Path is not a directory: {folder}")
        return issues
    
    # Find datasheet subfolders
    subfolders = [f for f in folder.iterdir() if f.is_dir()]
    
    if not subfolders:
        issues.append(f"No datasheet subfolders found in {folder}")
    
    for subfolder in subfolders:
        md_files = list(subfolder.glob("*.md"))
        
        if len(md_files) == 0:
            issues.append(f"[{subfolder.name}] No markdown file found")
        elif len(md_files) > 1:
            issues.append(f"[{subfolder.name}] Multiple markdown files: {[f.name for f in md_files]}")
    
    return issues

# Usage
if __name__ == "__main__":
    folder = Path(r"D:\datasheets")
    issues = validate_datasheet_folder(folder)
    
    if issues:
        print("❌ Validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("✅ Folder structure is valid")
        sys.exit(0)
```

**Run validation before ingestion**:
```bash
python validate-structure.py && python -m src.cli.ingest D:\datasheets
```

---

## Markdown Format Tips

### Best Practices for Datasheet Markdown

1. **Use Standard Markdown Syntax**:
   ```markdown
   # Main Heading (H1)
   ## Section Heading (H2)
   ### Subsection Heading (H3)
   
   Normal paragraph text.
   
   - Bullet list item 1
   - Bullet list item 2
   
   1. Numbered list item 1
   2. Numbered list item 2
   ```

2. **Tables** (Keep well-formatted):
   ```markdown
   | Pin | Name | Function | Voltage |
   |-----|------|----------|---------|
   | 1   | VCC  | Power    | 5V      |
   | 2   | GND  | Ground   | 0V      |
   | 3   | OUT  | Output   | 0-5V    |
   ```

3. **Code Blocks** (Use fencing):
   ```markdown
   Configuration example:
   
   ```c
   PORTB |= (1 << PB0);  // Set pin high
   DDRB |= (1 << PB0);   // Configure as output
   ```
   ```

4. **Images** (Use relative paths):
   ```markdown
   ![Pinout Diagram](./images/pinout.png)
   ![Schematic](./images/schematic.png)
   ```
   
   **Note**: Relative paths are automatically converted to absolute paths during ingestion.

5. **Avoid**:
   - HTML tags (use markdown syntax instead)
   - Complex nested tables
   - Very long lines (>1000 characters without line breaks)

---

## Querying Ingested Data (with Chroma MCP Server)

### Example: Semantic Search

```python
# query-example.py
import chromadb

client = chromadb.PersistentClient(path=r"D:\.cache\chromadb")
collection = client.get_collection("datasheets")

# Search for op-amp specifications
results = collection.query(
    query_texts=["op-amp input impedance specifications"],
    n_results=5
)

print("Top 5 results:")
for i, (doc, metadata, distance) in enumerate(zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
), 1):
    print(f"\n{i}. {metadata['datasheet_name']} (chunk {metadata['chunk_index']})")
    print(f"   Section: {metadata.get('section_heading', 'N/A')}")
    print(f"   Distance: {distance:.3f}")
    print(f"   Preview: {doc[:100]}...")
```

**Output**:
```
Top 5 results:

1. TL072 (chunk 3)
   Section: Electrical Characteristics
   Distance: 0.234
   Preview: ## Electrical Characteristics

| Parameter | Min | Typ | Max | Unit |
|-----------|-----|-----|-----...

2. LM358 (chunk 5)
   Section: DC Electrical Characteristics
   Distance: 0.312
   Preview: Input offset voltage: 2 mV (typ), 7 mV (max)
Input bias current: 45 nA (typ), 250 nA...
```

---

## Troubleshooting

### Issue: "No module named 'src'"

**Cause**: Running CLI from wrong directory or PYTHONPATH not set.

**Solution**:
```bash
# Ensure you're in project root
cd D:\Python\Projects\pdf-knowledgebase

# Run with -m flag (module mode)
python -m src.cli.ingest D:\datasheets
```

---

### Issue: "ChromaDB connection failed"

**Cause**: ChromaDB path inaccessible or doesn't exist.

**Solution**:
```bash
# Check if path exists
ls D:\.cache\chromadb

# Create directory if missing
New-Item -ItemType Directory -Path "D:\.cache\chromadb" -Force

# Or use custom path
$env:CHROMADB_PATH = "D:\chromadb"
python -m src.cli.ingest D:\datasheets
```

---

### Issue: "Memory error during embedding generation"

**Cause**: Too many datasheets being processed, exceeding available RAM.

**Solution**:
```bash
# Process in smaller batches
python -m src.cli.ingest D:\datasheets\batch1
python -m src.cli.ingest D:\datasheets\batch2
python -m src.cli.ingest D:\datasheets\batch3

# Or increase virtual memory (Windows)
# System Properties → Advanced → Performance Settings → Virtual Memory
```

---

### Issue: "Ingestion very slow (>60 seconds per datasheet)"

**Possible Causes and Solutions**:

1. **Large datasheets** (>50 pages):
   - Expected behavior (log warning and continue)
   - Consider splitting datasheet into multiple files

2. **First run** (downloading embedding model):
   - Wait for `sentence-transformers/all-MiniLM-L6-v2` to download (~80 MB)
   - Subsequent runs will be faster

3. **CPU bottleneck**:
   - Close other CPU-intensive applications
   - Future: Batch embedding optimization

4. **Disk I/O bottleneck**:
   - Move ChromaDB to SSD
   - Ensure antivirus isn't scanning ChromaDB folder

---

## Next Steps

After ingesting datasheets, you can:

1. **Query with Python**: Use ChromaDB client directly (see examples above)
2. **Query with MCP Server**: Use Chroma MCP Server for AI agent integration
3. **Build applications**: Integrate with LangChain for RAG pipelines
4. **Monitor collection**: Check ChromaDB dashboard (if available) or use scripts

---

## Additional Resources

- **ChromaDB Documentation**: https://docs.trychroma.com/
- **LangChain Documentation**: https://python.langchain.com/
- **Project Repository**: (Add your GitHub URL here)
- **Issue Tracker**: (Add your GitHub Issues URL here)

---

## Frequently Asked Questions

### Q: Can I use this pipeline on Linux or macOS?

**A**: Yes, the pipeline is designed to be cross-platform. However, primary testing is on Windows. Path handling uses `pathlib`, which is cross-platform compatible.

### Q: What if my datasheets are in PDF format?

**A**: This pipeline expects markdown input. You need to convert PDFs to markdown first using a separate tool (e.g., `pdftotext`, `pypdf`, or specialized PDF-to-markdown converters). This is a prerequisite step.

### Q: Can I customize the embedding model?

**A**: Not in v1.0. The pipeline uses ChromaDB's default embedding function (`sentence-transformers/all-MiniLM-L6-v2`). Custom embedding models are planned for future versions.

### Q: How do I delete a datasheet from ChromaDB?

**A**: Use the ChromaDB client directly:
```python
import chromadb

client = chromadb.PersistentClient(path=r"D:\.cache\chromadb")
collection = client.get_collection("datasheets")

# Delete all chunks for a datasheet
results = collection.get(where={"datasheet_name": "TL072"})
collection.delete(ids=results['ids'])
```

### Q: Can I run multiple ingestion processes in parallel?

**A**: No, the ChromaDB Python client is not thread-safe for writes. Run ingestions sequentially.

### Q: What happens if I interrupt ingestion (Ctrl+C)?

**A**: Partially ingested datasheets may have incomplete chunks in ChromaDB. Re-run ingestion with `--force-update` for affected datasheets to ensure consistency.

---

## Summary

✅ **Install dependencies** with `pip install -r requirements.txt`  
✅ **Prepare datasheets** in folder structure (one `.md` file per subfolder)  
✅ **Run ingestion** with `python -m src.cli.ingest <folder_path>`  
✅ **Use `--force-update`** to re-ingest existing datasheets  
✅ **Use `--log-level DEBUG`** for troubleshooting  
✅ **Query data** with ChromaDB client or Chroma MCP Server  

**Happy ingesting! 🚀**
