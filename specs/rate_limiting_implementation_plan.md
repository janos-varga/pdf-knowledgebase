# Rate Limiting Implementation Plan for RAGAS Evaluation

**Date:** 2026-01-16  
**Status:** Ready for Implementation  
**Target:** `src/evaluation/evaluate_rag.py`

---

## Problem Statement

Current async RAGAS evaluation triggers OpenAI rate limits (HTTP 429 errors) due to concurrent API requests exceeding Tier 1 limits.

### Current Behavior:
- Multiple QA pairs evaluated concurrently
- Each QA pair triggers 5 RAGAS metrics
- Each metric makes ~2-4 OpenAI API calls
- Total: ~15-20 API requests per QA pair
- **Result:** 150-200 concurrent requests → Rate limit exceeded

### OpenAI Tier 1 Limits:
- `gpt-4o-mini`: 200,000 TPM, **500 RPM** ← Bottleneck
- `gpt-5-mini`: 500,000 TPM, 500 RPM
- `text-embedding-3-small`: 1,000,000 TPM, 3,000 RPM

### Target Rate:
- 500 RPM = 8.3 requests/second
- **Safe target: 6-7 requests/second** (with margin)

---

## Solution: Semaphore-Based Rate Limiting

Use `asyncio.Semaphore` to control concurrent OpenAI API calls, keeping rate under 500 RPM.

### Configuration:
```python
MAX_CONCURRENT_API_CALLS = 6  # ~6 RPS (below 8.3 RPS limit)
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
```

---

## Implementation Steps

### Step 1: Add Rate Limiting Parameters to `__init__`

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** `KnowledgebaseEvaluator.__init__()` method

**Changes:**
1. Add new parameter `max_concurrent_api_calls: int = 6`
2. Create semaphore instance: `self.api_semaphore = asyncio.Semaphore(max_concurrent_api_calls)`
3. Store retry configuration as instance variables

**Code to add:**
```python
def __init__(
    self,
    datasheets_path: Path,
    qa_csv_path: Path,
    experiments_csv_path: Path,
    output_dir: Path,
    max_concurrent_api_calls: int = 6,  # NEW
):
    # ... existing code ...
    
    # Rate limiting configuration (NEW)
    self.max_concurrent_api_calls = max_concurrent_api_calls
    self.api_semaphore = asyncio.Semaphore(max_concurrent_api_calls)
    self.max_retries = 3
    self.initial_retry_delay = 1.0
```

**Lines affected:** ~61-100

---

### Step 2: Create Rate-Limited Metric Wrapper Method

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** New method in `KnowledgebaseEvaluator` class

**Purpose:** Wrap metric `.ascore()` calls with semaphore and retry logic

**Code to add:**
```python
async def _rate_limited_metric_call(
    self,
    metric_func,
    metric_name: str,
    **kwargs,
):
    """
    Execute metric scoring with rate limiting and retry logic.
    
    Args:
        metric_func: Async metric scoring function (e.g., metric.ascore)
        metric_name: Name of metric for logging
        **kwargs: Arguments to pass to metric function
        
    Returns:
        Metric result
        
    Raises:
        Exception: If all retries exhausted
    """
    retry_delay = self.initial_retry_delay
    
    for attempt in range(self.max_retries):
        try:
            async with self.api_semaphore:
                logger.debug(
                    f"[{metric_name}] Acquiring semaphore "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                result = await metric_func(**kwargs)
                logger.debug(f"[{metric_name}] Success")
                return result
                
        except Exception as e:
            error_str = str(e)
            
            # Check if rate limit error
            if "429" in error_str or "rate_limit" in error_str.lower():
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"[{metric_name}] Rate limit hit, "
                        f"retrying in {retry_delay}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(
                        f"[{metric_name}] Rate limit - all retries exhausted"
                    )
                    raise
            else:
                # Non-rate-limit error, raise immediately
                logger.error(f"[{metric_name}] Error: {e}")
                raise
    
    raise RuntimeError(f"[{metric_name}] Failed after {self.max_retries} attempts")
```

**Location:** After `query_rag()` method, before `generate_rag_responses()`  
**Lines to add:** ~60 lines

---

### Step 3: Wrap Metric Calls with Rate Limiter

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** Inside `run_evaluation()` async function (nested in `evaluate_experiment()`)

**Changes:** Replace direct `.ascore()` calls with `_rate_limited_metric_call()`

**Current code (lines ~331-355):**
```python
# Current - WITHOUT rate limiting
faith_result = await faithfulness.ascore(
    user_input=row.user_input,
    response=row.response,
    retrieved_contexts=row.retrieved_contexts,
)

relevancy_result = await answer_relevancy.ascore(
    user_input=row.user_input,
    response=row.response,
)

# ... etc for all 5 metrics
```

**New code:**
```python
# NEW - WITH rate limiting
faith_result = await self._rate_limited_metric_call(
    faithfulness.ascore,
    "Faithfulness",
    user_input=row.user_input,
    response=row.response,
    retrieved_contexts=row.retrieved_contexts,
)

relevancy_result = await self._rate_limited_metric_call(
    answer_relevancy.ascore,
    "AnswerRelevancy",
    user_input=row.user_input,
    response=row.response,
)

correctness_result = await self._rate_limited_metric_call(
    factual_correctness.ascore,
    "FactualCorrectness",
    response=row.response,
    reference=row.reference,
)

context_rel_result = await self._rate_limited_metric_call(
    context_relevance.ascore,
    "ContextRelevance",
    user_input=row.user_input,
    retrieved_contexts=row.retrieved_contexts,
)

summary_result = await self._rate_limited_metric_call(
    summary_score.ascore,
    "SummaryScore",
    reference_contexts=row.retrieved_contexts,
    response=row.response,
)
```

**Lines affected:** ~331-355 (25 lines modified)

---

### Step 4: Add Progress Logging

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** In `evaluate_experiment()` method, before running evaluation

**Purpose:** Log progress during evaluation to monitor rate limiting

**Code to add (after line ~309):**
```python
logger.info("Running RAGAS evaluation...")
logger.info(
    f"Rate limiting: max {self.max_concurrent_api_calls} concurrent API calls"
)
logger.info(f"Processing {len(samples)} QA pairs with 5 metrics each")
logger.info(f"Estimated API calls: ~{len(samples) * 15}")
```

**Lines to add:** ~4 lines

---

### Step 5: Add Evaluation Timing Metrics

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** In `evaluate_experiment()` method, around evaluation execution

**Purpose:** Track and log actual evaluation time with rate limiting

**Code to modify (around lines ~368-372):**
```python
# Current
experiment_results = asyncio.run(
    run_evaluation.arun(evaluation_dataset, backend="inmemory")
)

# NEW - Add timing
eval_start_time = time.time()
experiment_results = asyncio.run(
    run_evaluation.arun(evaluation_dataset, backend="inmemory")
)
eval_duration = time.time() - eval_start_time

logger.info(f"Evaluation completed in {eval_duration:.2f}s")
logger.info(
    f"Average time per QA pair: {eval_duration / len(samples):.2f}s"
)
```

**Lines affected:** ~368-376 (add timing wrapper)

**Note:** Add `import time` at top of file if not already present

---

### Step 6: Update Docstring and Add Configuration Note

**File:** `src/evaluation/evaluate_rag.py`  
**Location:** `KnowledgebaseEvaluator` class docstring

**Changes:** Document new rate limiting parameter

**Code to modify (around line ~58-80):**
```python
class KnowledgebaseEvaluator:
    """
    Evaluates the Knowledgebase using RAGAS metrics.
    
    Includes rate limiting to prevent OpenAI API 429 errors when
    evaluating multiple QA pairs concurrently.
    """

    def __init__(
        self,
        datasheets_path: Path,
        qa_csv_path: Path,
        experiments_csv_path: Path,
        output_dir: Path,
        max_concurrent_api_calls: int = 6,
    ):
        """
        Initialize evaluator.

        Args:
            datasheets_path: Path to datasheets folder
            qa_csv_path: Path to Q&A pairs CSV
            experiments_csv_path: Path to experiments config CSV
            output_dir: Directory for evaluation logs
            max_concurrent_api_calls: Maximum concurrent OpenAI API calls
                                     (default: 6, safe for Tier 1 500 RPM limit)
        """
```

**Lines affected:** ~58-80

---

## Summary of Changes

### Files Modified:
- `src/evaluation/evaluate_rag.py`

### Changes:
1. ✅ Add `max_concurrent_api_calls` parameter to `__init__` (~5 lines)
2. ✅ Add semaphore and retry configuration to `__init__` (~4 lines)
3. ✅ Create `_rate_limited_metric_call()` method (~60 lines)
4. ✅ Wrap 5 metric calls with rate limiter (~25 lines modified)
5. ✅ Add progress logging (~4 lines)
6. ✅ Add evaluation timing metrics (~6 lines)
7. ✅ Update docstrings (~10 lines)

**Total lines added/modified:** ~114 lines

---

## Expected Performance

### Before Rate Limiting:
- 10 QA pairs → 150-200 concurrent requests
- Rate limit errors (429)
- Unpredictable completion time (2-3 minutes with retries)

### After Rate Limiting:
- 10 QA pairs → Max 6 concurrent requests at any time
- **No rate limit errors** ✓
- Predictable completion time: **~25-30 seconds**
- Per QA pair: ~2.5 seconds (15 calls ÷ 6 concurrent)

### Scaling:
- 50 QA pairs: ~125-150 seconds (2-2.5 minutes)
- 100 QA pairs: ~250-300 seconds (4-5 minutes)

---

## Post-Implementation Validation Checklist

### 1. Code Quality Checks
- [ ] All imports are present (`asyncio`, `time`)
- [ ] No syntax errors
- [ ] Type hints are correct
- [ ] Docstrings are complete
- [ ] Logger statements use correct format
- [ ] Code follows project style (PEP 8, line length 88)

### 2. Functional Validation

#### 2.1 Basic Functionality
- [ ] Script runs without errors: `uv run python -m src.evaluation.evaluate_rag`
- [ ] Semaphore is created in `__init__`
- [ ] `_rate_limited_metric_call()` method exists
- [ ] All 5 metric calls use `_rate_limited_metric_call()`

#### 2.2 Rate Limiting Behavior
- [ ] Log shows "Rate limiting: max 6 concurrent API calls" message
- [ ] Debug logs show "[MetricName] Acquiring semaphore" messages
- [ ] No HTTP 429 errors in logs
- [ ] OpenAI client logs show no retry messages for rate limits

#### 2.3 Retry Logic
- [ ] Simulated 429 error triggers retry (manual test)
- [ ] Exponential backoff works (1s, 2s, 4s delays)
- [ ] After max retries, exception is raised
- [ ] Non-429 errors fail immediately (no retries)

#### 2.4 Performance Validation
- [ ] Evaluation completes successfully
- [ ] Timing metrics logged: "Evaluation completed in X.XXs"
- [ ] Average time per QA pair is reasonable (~2-3 seconds)
- [ ] Total time matches expectations (QA_count × 2.5s)

#### 2.5 Progress Logging
- [ ] Shows total QA pairs being processed
- [ ] Shows estimated API calls count
- [ ] Shows rate limiting configuration
- [ ] Shows completion time and average

### 3. Integration Tests

#### Test Case 1: Small Dataset (3 QA pairs)
```bash
# Prepare test dataset with 3 QA pairs
uv run python -m src.evaluation.evaluate_rag
```

**Expected:**
- [ ] Completes in ~7-10 seconds
- [ ] No 429 errors
- [ ] All 3 QA pairs evaluated successfully
- [ ] Metrics results are valid (0.0-1.0 range)

#### Test Case 2: Medium Dataset (10 QA pairs)
```bash
# Full dataset
uv run python -m src.evaluation.evaluate_rag
```

**Expected:**
- [ ] Completes in ~25-30 seconds
- [ ] No 429 errors
- [ ] All 10 QA pairs evaluated successfully
- [ ] Results saved to output directory

#### Test Case 3: Custom Rate Limit
```python
# Modify test to use different semaphore value
evaluator = KnowledgebaseEvaluator(
    ...,
    max_concurrent_api_calls=3  # More conservative
)
```

**Expected:**
- [ ] Evaluation is slower (2x time)
- [ ] No errors
- [ ] Validates parameter is configurable

### 4. Error Handling Tests

#### Test Case 4: Simulate Rate Limit Error
```python
# Temporarily set max_concurrent_api_calls=100 to force 429
```

**Expected:**
- [ ] 429 errors are caught
- [ ] Retry logic activates
- [ ] Exponential backoff delays observed
- [ ] Eventually succeeds or fails gracefully

#### Test Case 5: Network Error During Evaluation
```python
# Disconnect network mid-evaluation
```

**Expected:**
- [ ] Non-rate-limit errors fail immediately
- [ ] Clear error message in logs
- [ ] Partial results are preserved (if any)

### 5. Code Inspection Checklist

#### Review `_rate_limited_metric_call()`:
- [ ] Semaphore acquired correctly (`async with`)
- [ ] Exception handling covers 429 errors
- [ ] Retry logic uses exponential backoff
- [ ] Non-429 errors are raised immediately
- [ ] Logging is informative (shows attempts)

#### Review `run_evaluation()` modifications:
- [ ] All 5 metrics wrapped with rate limiter
- [ ] Correct parameters passed to wrapper
- [ ] Metric names are descriptive
- [ ] Function still returns `MetricsResult`

#### Review `__init__()` modifications:
- [ ] Semaphore initialized correctly
- [ ] Default value is 6 (safe for Tier 1)
- [ ] Docstring documents new parameter
- [ ] Retry config stored as instance variables

### 6. Regression Tests
- [ ] Existing tests still pass (if any)
- [ ] Evaluation results are consistent with pre-rate-limiting
- [ ] No breaking changes to public API
- [ ] Backward compatible (default parameter)

### 7. Documentation Checks
- [ ] Class docstring updated
- [ ] Method docstrings are complete
- [ ] Parameter descriptions are clear
- [ ] Usage examples are correct (if any)
- [ ] This implementation plan marked as "COMPLETED"

### 8. Performance Benchmarks

Record baseline metrics:
- [ ] **QA pairs processed:** _____
- [ ] **Total evaluation time:** _____ seconds
- [ ] **Average per QA pair:** _____ seconds
- [ ] **Total API calls made:** _____
- [ ] **Rate limit errors:** 0 ✓
- [ ] **OpenAI retries:** 0 ✓

Compare with pre-implementation (if available):
- [ ] Time difference: _____ (acceptable if < 2x)
- [ ] Reliability improvement: 100% (no 429s)

### 9. Edge Cases
- [ ] Empty QA dataset (0 pairs) - should handle gracefully
- [ ] Single QA pair - should work
- [ ] Large dataset (50+ pairs) - should scale linearly
- [ ] All metrics fail - should raise clear error

### 10. Final Validation
- [ ] Run linter: `uv tool run ruff check src/evaluation/evaluate_rag.py`
- [ ] Run type checker: `uv tool run mypy src/evaluation/evaluate_rag.py`
- [ ] Run formatter: `uv tool run black src/evaluation/evaluate_rag.py`
- [ ] All checks pass ✓

---

## Rollback Plan

If issues occur after implementation:

1. **Quick fix:** Set `max_concurrent_api_calls=1` for sequential execution
2. **Full rollback:** Revert all changes using git:
   ```bash
   git checkout src/evaluation/evaluate_rag.py
   ```
3. **Alternative:** Add simple delay between metric calls:
   ```python
   await asyncio.sleep(0.5)  # After each metric
   ```

---

## Configuration Tuning Guide

If you still see 429 errors after implementation:

1. **Decrease concurrency:**
   ```python
   max_concurrent_api_calls=4  # More conservative
   ```

2. **Increase retry delay:**
   ```python
   self.initial_retry_delay = 2.0  # Start with 2s
   ```

3. **Add batch delays** (if needed):
   Process QA pairs in batches with delays between batches.

If evaluation is too slow:

1. **Increase concurrency (carefully):**
   ```python
   max_concurrent_api_calls=8  # Slightly more aggressive
   ```

2. **Monitor OpenAI dashboard** for actual usage rates

---

## Success Criteria

✅ **Implementation is successful if:**
1. No HTTP 429 errors in logs
2. Evaluation completes successfully
3. Performance is predictable (~2.5s per QA pair)
4. Code passes linting/type checking
5. All validation checklist items pass

---

## Notes for Implementation

- Use descriptive variable names
- Add debug logging at key points
- Test with small dataset first
- Monitor OpenAI API dashboard during testing
- Keep semaphore value configurable for different OpenAI tiers

---

## References

- OpenAI Rate Limits: https://platform.openai.com/docs/guides/rate-limits
- asyncio.Semaphore: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- RAGAS Documentation: https://docs.ragas.io/

---

**Status:** Ready for implementation  
**Estimated implementation time:** 30-45 minutes  
**Estimated testing time:** 15-30 minutes
