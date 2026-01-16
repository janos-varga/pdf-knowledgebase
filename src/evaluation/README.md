# Performance Tuning and Evaluation

This folder contains scripts and data for evaluating and tuning chunking configurations using RAGAS metrics.

## Files

- **`evaluate_rag.py`**: Main evaluation script that runs experiments with different chunk sizes
- **`experiments.csv`**: Configuration file for chunking experiments (semicolon-delimited)
- **`datasheet_qa.csv`**: Question-answer pairs for evaluation (comma-delimited)
- **`evaluation_*.log`**: Detailed logs from evaluation runs
- **`evaluation_results_*.json`**: JSON results from experiments

## Quick Start

### 1. Configure Experiments

Edit `experiments.csv` to define chunking configurations.

**Column Headers**: Headers are converted to snake_case (e.g., `chunk-size` → `chunk_size`) 
and passed as keyword arguments to `ingest_batch()`. 
This allows you to control any pipeline parameter exposed in the CLI without modifying code.

**Supported Parameters**: Any parameter accepted by `ingest_batch()` in `src/ingestion/pipeline.py` can be configured:
- `chunk-size` (required): Target chunk size in tokens
- `chunk-overlap` (required): Chunk overlap in tokens
- `force-update`: Set to `true` to force re-ingestion (future use)

Example:

```csv
chunk-size,chunk-overlap
512,50
1024,100
1024,150
2048,200
2048,300
```

### 2. Run Evaluation

```bash
uv run python evaluation/evaluate_rag.py
```

### 3. Review Results

Results are saved to:
- **JSON**: `evaluation/evaluation_results_YYYYMMDD_HHMMSS.json`
- **Log**: `evaluation/evaluation_YYYYMMDD_HHMMSS.log`

## How It Works

### Evaluation Pipeline

1. **Ingest Datasheets**: Load datasheets into in-memory ChromaDB with specified chunk size/overlap
2. **Generate Responses**: Query RAG system for each question using gpt-5-mini
3. **Evaluate Metrics**: Calculate RAGAS metrics using the @experiment decorator (RAGAS v0.4+), see below.

The evaluation uses RAGAS's new @experiment decorator approach for better tracking and structured results.

### RAGAS Metrics

- **Faithfulness**: Assesses whether all claims in the generated answer can be inferred directly from the provided context (0.0-1.0)
  - Higher = fewer hallucinations, better grounding in context
- **Answer Relevancy**: Measures how relevant the answer is to the question (0.0-1.0)
  - Higher = more relevant and on-topic answers
- **Factual Correctness**: Checks the factual accuracy of the generated response by comparing it with a reference (0.0-1.0)
  - Higher = more accurate answers
- **Context Relevance**: Evaluates how relevant the retrieved contexts are to the question (0.0-1.0)
  - Higher = better retrieval quality
- **Summary Score**: Overall quality score of the response based on multiple factors (0.0-1.0)
  - Higher = better overall response quality

## Configuration

### experiments.csv Format

```csv
chunk-size,chunk-overlap
<int>,<int>
```

- **chunk-size**: Target chunk size in tokens
- **chunk-overlap**: Overlap between chunks in tokens
- **Delimiter**: Comma (`,`)

### datasheet_qa.csv Format

```csv
question,answer
"Question text","Answer text"
```

- **question**: Question to ask the RAG system
- **answer**: Ground truth answer (reference)
- **Delimiter**: Comma (`,`)
- **Quoting**: CSV standard quoting

## Results Format

```json
{
  "experiment_id": 1,
  "chunk_size": 1024,
  "chunk_overlap": 100,
  "timestamp": "2026-01-14T23:00:00",
  "duration_seconds": 123.45,
  "num_qa_pairs": 110,
  "metrics": {
    "llm_context_recall": 0.85,
    "faithfulness": 0.92,
    "factual_correctness": 0.78
  },
  "status": "success"
}
```

## Requirements

- Python 3.13+
- Dependencies:
  - `ragas` (v0.4+)
  - `langchain-openai`
  - `chromadb`
  - `pydantic`
  - OpenAI API key in environment

## Tips

- **Start small**: Test with 2-3 configurations first
- **Monitor costs**: Each experiment makes multiple LLM calls
- **Check logs**: Review `.log` files for detailed progress
- **Compare results**: Use JSON output for comparative analysis
