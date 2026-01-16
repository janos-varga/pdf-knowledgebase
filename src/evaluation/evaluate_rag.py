"""
RAGAS-based performance tuning and evaluation script.

This script evaluates different Knowledgebase configurations by:
1. Ingesting datasheets into in-memory ChromaDB with various chunk sizes/overlaps
2. Running question-answer evaluation using RAGAS metrics with @experiment decorator
3. Logging results for analysis

Uses the new RAGAS v0.4+ @experiment decorator approach for structured evaluation.

Dependencies:
    - ragas (v0.4+)
    - langchain-openai
    - chromadb
    - pydantic
"""

import asyncio
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel
from ragas import EvaluationDataset, experiment
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextRelevance,
    FactualCorrectness,
    Faithfulness,
    SummaryScore,
)

from src.cli.ingest import ingest
from src.ingestion.chroma_client import ChromaDBClient

logger = logging.getLogger("evaluation")

OPENAI_MODEL_NAME = "gpt-4o-mini"


class MetricsResult(BaseModel):
    """Results structure for RAGAS metrics."""

    faithfulness: float
    answer_relevancy: float
    factual_correctness: float
    context_relevance: float
    summary_score: float


class KnowledgebaseEvaluator:
    """Evaluates the Knowledgebase using RAGAS metrics."""

    def __init__(
        self,
        datasheets_path: Path,
        qa_csv_path: Path,
        experiments_csv_path: Path,
        output_dir: Path,
    ):
        """
        Initialize evaluator.

        Args:
            datasheets_path: Path to datasheets folder
            qa_csv_path: Path to Q&A pairs CSV
            experiments_csv_path: Path to experiments config CSV
            output_dir: Directory for evaluation logs
        """
        self.datasheets_path = datasheets_path
        self.qa_csv_path = qa_csv_path
        self.experiments_csv_path = experiments_csv_path
        self.output_dir = output_dir

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize LLM for response generation
        self.response_llm = ChatOpenAI(model=OPENAI_MODEL_NAME, temperature=0)

        # Initialize OpenAI clients for RAGAS
        # Use AsyncOpenAI for async evaluation metrics and embeddings
        async_openai_client = AsyncOpenAI()

        # Initialize RAGAS LLM using llm_factory with async client
        self.evaluator_llm = llm_factory(
            model=OPENAI_MODEL_NAME, client=async_openai_client, temperature=0
        )

        # Initialize embeddings with async client for metrics that need them (AnswerRelevancy)
        self.embeddings = OpenAIEmbeddings(
            client=async_openai_client, model="text-embedding-3-small"
        )

        logger.info("KnowledgebaseEvaluator initialized")

    def load_experiments(self) -> list[dict[str, Any]]:
        """
        Load experiment configurations from CSV.

        Column headers in experiments.csv are converted to snake_case and used
        as keyword arguments for ingest_batch(). This allows complete control
        of pipeline parameters from the CSV without code changes.

        Example CSV:
            chunk-size,chunk-overlap
            512,50
            1024,100

        Returns:
            List of experiment configs as kwargs dicts for ingest_batch()
        """
        experiments = []
        with open(self.experiments_csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                # Convert CSV headers (kebab-case) to Python kwargs (snake_case)
                # and convert values to appropriate types
                experiment_params = {}
                for key, value in row.items():
                    # Convert "chunk-size" to "chunk_size"
                    param_name = key.replace("-", "_")

                    # Try to convert to int, fallback to string
                    try:
                        experiment_params[param_name] = int(value)
                    except ValueError:
                        # Keep as string for non-numeric values
                        experiment_params[param_name] = value

                experiments.append(experiment_params)
        logger.info(f"Loaded {len(experiments)} experiment configurations")
        return experiments

    def load_qa_pairs(self) -> list[dict[str, str]]:
        """
        Load question-answer pairs from CSV.

        Returns:
            List of Q&A pairs with question and answer fields
        """
        qa_pairs = []
        with open(self.qa_csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qa_pairs.append(
                    {
                        "question": row["question"],
                        "answer": row["answer"],
                    }
                )
        logger.info(f"Loaded {len(qa_pairs)} Q&A pairs")
        return qa_pairs

    def ingest_datasheets(self, **ingestion_params) -> ChromaDBClient:
        """
        Ingest datasheets into in-memory ChromaDB using the robust ingest() function.

        This now benefits from all error handling and validation in src.cli.ingest,
        including proper exception handling, validation, and logging.

        Args:
            **ingestion_params: Keyword arguments passed to ingest()
                               (e.g., chunk_size, chunk_overlap, force_update)

        Returns:
            ChromaDB client with ingested data

        Raises:
            FileNotFoundError: If datasheets folder doesn't exist
            ValueError: If folder structure is invalid or no datasheets found
            RuntimeError: If ChromaDB initialization or ingestion fails
        """
        params_str = ", ".join(f"{k}={v}" for k, v in ingestion_params.items())
        logger.info(f"Ingesting datasheets ({params_str})...")

        # Use the robust ingest() function with ephemeral ChromaDB
        report, chroma_client = ingest(
            datasheets_folder_path=self.datasheets_path,
            persist_db=False,  # Always use ephemeral for evaluation
            force_update=True,
            **ingestion_params,
        )

        logger.info(
            f"Ingestion complete: {report.successful} successful, {report.failed} failed"
        )

        if report.failed > 0:
            logger.warning(f"Some datasheets failed to ingest: {report.failed}")
            # Don't raise exception - evaluation can continue with partial data

        return chroma_client

    def query_rag(
        self, chroma_client: ChromaDBClient, question: str, n_results: int = 5
    ) -> tuple[str, list[str]]:
        """
        Query RAG system and get response with contexts.

        Args:
            chroma_client: ChromaDB client
            question: Question to ask
            n_results: Number of contexts to retrieve

        Returns:
            Tuple of (generated_response, retrieved_contexts)
        """
        # Query ChromaDB for relevant contexts
        results = chroma_client.collection.query(
            query_texts=[question], n_results=n_results
        )

        # Extract contexts
        contexts = results["documents"][0] if results["documents"] else []

        # Generate response using LLM with retrieved contexts
        if contexts:
            context_text = "\n\n".join(contexts)
            prompt = f"""Based on the following datasheet information, answer the question.

Context from datasheets:
{context_text}

Question: {question}

Answer:"""
            response = self.response_llm.invoke(prompt).content
        else:
            response = "No relevant information found in datasheets."

        return response, contexts

    def generate_rag_responses(
        self, chroma_client: ChromaDBClient, qa_pairs: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """
        Generate RAG responses for all Q&A pairs.

        Args:
            chroma_client: ChromaDB client
            qa_pairs: List of Q&A pairs

        Returns:
            List of samples for RAGAS evaluation
        """
        samples = []

        for qa in qa_pairs:
            question = qa["question"]
            reference = qa["answer"]

            # Query RAG
            response, contexts = self.query_rag(chroma_client, question)

            # Create RAGAS sample
            sample = {
                "user_input": question,
                "retrieved_contexts": contexts,
                "response": response,
                "reference": reference,
            }
            samples.append(sample)

        logger.info(f"Generated {len(samples)} RAG responses")
        return samples

    def evaluate_experiment(
        self,
        experiment_id: int,
        qa_pairs: list[dict[str, str]],
        **experiment_params,
    ) -> dict[str, Any]:
        """
        Run single experiment evaluation.

        Args:
            experiment_id: Experiment identifier
            qa_pairs: Q&A pairs for evaluation
            **experiment_params: Dynamic pipeline parameters from experiments.csv
                                (e.g., chunk_size, chunk_overlap, force_update)

        Returns:
            Evaluation results dictionary
        """
        start_time = datetime.now()
        params_str = ", ".join(f"{k}={v}" for k, v in experiment_params.items())
        logger.info(f"\n{'='*70}")
        logger.info(f"Experiment {experiment_id}: {params_str}")
        logger.info(f"{'='*70}")

        try:
            # Step 1: Ingest datasheets
            chroma_client = self.ingest_datasheets(**experiment_params)

            # Step 2: Generate RAG responses
            samples = self.generate_rag_responses(chroma_client, qa_pairs)

            # Step 3: Create RAGAS evaluation dataset
            evaluation_dataset = EvaluationDataset.from_list(samples)

            # Step 4: Evaluate with RAGAS using @experiment decorator
            logger.info("Running RAGAS evaluation...")

            # Define the experiment function with decorator
            @experiment(MetricsResult)
            async def run_evaluation(row):
                """Evaluate single row with all metrics."""
                try:
                    # Log the row type for debugging
                    logger.debug(f"Processing row of type: {type(row)}")
                    logger.debug(f"Row attributes: {dir(row)}")

                    # Initialize metrics with LLM and embeddings
                    faithfulness = Faithfulness(llm=self.evaluator_llm)
                    answer_relevancy = AnswerRelevancy(
                        llm=self.evaluator_llm, embeddings=self.embeddings
                    )
                    factual_correctness = FactualCorrectness(llm=self.evaluator_llm)
                    context_relevance = ContextRelevance(llm=self.evaluator_llm)
                    summary_score = SummaryScore(llm=self.evaluator_llm)

                    # Score each metric
                    faith_result = await faithfulness.ascore(
                        user_input=row.user_input,
                        response=row.response,
                        retrieved_contexts=row.retrieved_contexts,
                    )

                    relevancy_result = await answer_relevancy.ascore(
                        user_input=row.user_input,
                        response=row.response,
                    )

                    correctness_result = await factual_correctness.ascore(
                        response=row.response,
                        reference=row.reference,
                    )

                    context_rel_result = await context_relevance.ascore(
                        user_input=row.user_input,
                        retrieved_contexts=row.retrieved_contexts,
                    )

                    summary_result = await summary_score.ascore(
                        reference_contexts=row.retrieved_contexts,
                        response=row.response,
                    )

                    return MetricsResult(
                        faithfulness=faith_result.value,
                        answer_relevancy=relevancy_result.value,
                        factual_correctness=correctness_result.value,
                        context_relevance=context_rel_result.value,
                        summary_score=summary_result.value,
                    )
                except Exception as e:
                    logger.error(f"Failed to evaluate row: {e}", exc_info=True)
                    raise  # Re-raise to let experiment framework handle it

            # Run evaluation asynchronously using arun with in-memory backend
            # Type ignore: EvaluationDataset is compatible but has different type hint
            experiment_results = asyncio.run(
                run_evaluation.arun(evaluation_dataset, backend="inmemory")  # type: ignore[arg-type]
            )

            # Extract MetricsResult objects from experiment
            metrics_list = list(experiment_results)

            # Check if we have any successful results
            if not metrics_list:
                raise ValueError(
                    "All evaluation tasks failed. Check the logs for individual task errors."
                )

            # Calculate average metrics across all samples
            avg_metrics = {
                "faithfulness": sum(r.faithfulness for r in metrics_list)
                / len(metrics_list),
                "answer_relevancy": sum(r.answer_relevancy for r in metrics_list)
                / len(metrics_list),
                "factual_correctness": sum(r.factual_correctness for r in metrics_list)
                / len(metrics_list),
                "context_relevance": sum(r.context_relevance for r in metrics_list)
                / len(metrics_list),
                "summary_score": sum(r.summary_score for r in metrics_list)
                / len(metrics_list),
            }

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Compile results
            results = {
                "experiment_id": experiment_id,
                **experiment_params,  # Include all experiment parameters dynamically
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "num_qa_pairs": len(qa_pairs),
                "metrics": avg_metrics,
                "status": "success",
            }

            logger.info(f"Experiment {experiment_id} completed successfully")
            logger.info(f"  Duration: {duration:.2f}s")
            logger.info(f"  Faithfulness: {results['metrics']['faithfulness']:.4f}")
            logger.info(
                f"  Answer Relevancy: {results['metrics']['answer_relevancy']:.4f}"
            )
            logger.info(
                f"  Factual Correctness: {results['metrics']['factual_correctness']:.4f}"
            )
            logger.info(
                f"  Context Relevance: {results['metrics']['context_relevance']:.4f}"
            )
            logger.info(f"  Summary Score: {results['metrics']['summary_score']:.4f}")

            return results

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(f"Experiment {experiment_id} failed: {e}", exc_info=True)

            return {
                "experiment_id": experiment_id,
                **experiment_params,  # Include all experiment parameters dynamically
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "num_qa_pairs": len(qa_pairs),
                "metrics": {
                    "faithfulness": None,
                    "answer_relevancy": None,
                    "factual_correctness": None,
                    "context_relevance": None,
                    "summary_score": None,
                },
                "status": "failed",
                "error": str(e),
            }

    def run_all_experiments(self):
        """Run all experiments and save results."""
        logger.info("Starting chunker tuning experiments...")

        # Load configurations
        experiments = self.load_experiments()
        qa_pairs = self.load_qa_pairs()

        # Run experiments
        all_results = []
        for i, exp in enumerate(experiments, start=1):
            results = self.evaluate_experiment(
                experiment_id=i,
                qa_pairs=qa_pairs,
                **exp,
            )
            all_results.append(results)

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"evaluation_results_{timestamp}.json"

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

        logger.info(f"\nResults saved to {results_file}")

        # Print summary
        self._print_summary(all_results)

    @staticmethod
    def _print_summary(results: list[dict[str, Any]]):
        """Print evaluation summary."""
        logger.info("\n" + "=" * 70)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 70)

        for result in results:
            status = "✓" if result["status"] == "success" else "✗"
            logger.info(f"\n{status} Experiment {result['experiment_id']}:")

            # Print experiment parameters dynamically (skip non-param fields)
            skip_fields = {"experiment_id", "timestamp", "duration_seconds",
                          "num_qa_pairs", "metrics", "status", "error"}
            for key, value in result.items():
                if key not in skip_fields:
                    # Convert snake_case to Title Case for display
                    display_name = key.replace("_", " ").title()
                    logger.info(f"  {display_name}: {value}")

            logger.info(f"  Duration: {result['duration_seconds']:.2f}s")

            if result["status"] == "success":
                logger.info(f"  Faithfulness: {result['metrics']['faithfulness']:.4f}")
                logger.info(
                    f"  Answer Relevancy: {result['metrics']['answer_relevancy']:.4f}"
                )
                logger.info(
                    f"  Factual Correctness: {result['metrics']['factual_correctness']:.4f}"
                )
                logger.info(
                    f"  Context Relevance: {result['metrics']['context_relevance']:.4f}"
                )
                logger.info(
                    f"  Summary Score: {result['metrics']['summary_score']:.4f}"
                )
            else:
                logger.info(f"  Error: {result.get('error', 'Unknown error')}")

        logger.info("\n" + "=" * 70)


def main():
    """Main entry point."""
    # Create evaluation directory if it doesn't exist
    output_dir = Path(__file__).parent / "eval_logs"
    output_dir.mkdir(exist_ok=True)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                output_dir
                / f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            ),
        ],
    )

    # Paths
    datasheets_path = Path(
        r"d:\Profiles\Janos\Dropbox\Autó\can-sniff\pi-hat\datasheets-md"
    )
    qa_csv_path = Path(__file__).parent / "datasheet_qa.csv"
    experiments_csv_path = Path(__file__).parent / "experiments.csv"

    # Run evaluation
    evaluator = KnowledgebaseEvaluator(
        datasheets_path=datasheets_path,
        qa_csv_path=qa_csv_path,
        experiments_csv_path=experiments_csv_path,
        output_dir=output_dir,
    )

    evaluator.run_all_experiments()


if __name__ == "__main__":
    main()
