"""
Quick test run with minimal configuration.

This script runs a single experiment with a small subset of Q&A pairs
to verify the setup works before running full evaluations.
"""

import logging
import sys
from pathlib import Path

from src.evaluation.evaluate_rag import KnowledgebaseEvaluator

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Changed to DEBUG to see detailed errors
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Enable DEBUG logging for ragas to see detailed errors
logging.getLogger("ragas").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def quick_test():
    """Run a quick test with first 5 Q&A pairs."""
    logger.info("Starting quick test run...")

    # Paths
    datasheets_path = Path(
        r"d:\Profiles\Janos\Dropbox\Autó\can-sniff\pi-hat\datasheets-md\1n4148"
    )
    qa_csv_path = Path("evaluation/datasheet_qa.csv")
    experiments_csv_path = Path("evaluation/experiments.csv")
    output_dir = Path("evaluation")

    # Create evaluator
    evaluator = KnowledgebaseEvaluator(
        datasheets_path=datasheets_path,
        qa_csv_path=qa_csv_path,
        experiments_csv_path=experiments_csv_path,
        output_dir=output_dir,
    )

    # Load Q&A pairs (limit to first 5)
    all_qa_pairs = evaluator.load_qa_pairs()
    qa_pairs_subset = all_qa_pairs[:5]
    logger.info(f"Using {len(qa_pairs_subset)} Q&A pairs for testing")

    # Run single experiment with default settings
    chunk_size = 1024
    chunk_overlap = 100

    result = evaluator.evaluate_experiment(
        experiment_id=0,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        qa_pairs=qa_pairs_subset,
    )

    # Print result
    logger.info("\n" + "=" * 70)
    logger.info("QUICK TEST RESULT")
    logger.info("=" * 70)
    logger.info(f"Status: {result['status']}")
    logger.info(f"Duration: {result['duration_seconds']:.2f}s")

    if result["status"] == "success":
        logger.info(f"Faithfulness: {result['metrics']['faithfulness']:.4f}")
        logger.info(
            f"Answer Relevancy: {result['metrics']['answer_relevancy']:.4f}"
        )
        logger.info(
            f"Factual Correctness: {result['metrics']['factual_correctness']:.4f}"
        )
        logger.info(
            f"Context Relevance: {result['metrics']['context_relevance']:.4f}"
        )
        logger.info(f"Summary Score: {result['metrics']['summary_score']:.4f}")
        logger.info("\nQuick test PASSED! Ready for full evaluation.")
    else:
        logger.error(f"Quick test FAILED: {result.get('error')}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(quick_test())
