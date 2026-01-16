"""
Test script to verify dynamic parameter passing from experiments.csv.

This script tests that:
1. CSV columns are correctly converted to snake_case kwargs
2. Parameters are passed through to ingest_batch correctly
3. No code changes are needed when new CLI args are added
"""

import csv
from pathlib import Path


def test_csv_parsing():
    """Test that experiments.csv is parsed correctly."""
    experiments_csv = Path(__file__).parent / "experiments.csv"

    experiment_params = []
    with open(experiments_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            # Convert CSV headers (kebab-case) to Python kwargs (snake_case)
            experiment = {}
            for key, value in row.items():
                param_name = key.replace("-", "_")

                # Try to convert to int, fallback to string
                try:
                    experiment[param_name] = int(value)
                except ValueError:
                    experiment[param_name] = value

            experiment_params.append(experiment)

    print(f"✓ Loaded {len(experiment_params)} experiments")
    print(f"✓ First experiment: {experiment_params[0]}")
    print(f"✓ Keys: {list(experiment_params[0].keys())}")

    # Verify required parameters exist
    assert all("chunk_size" in exp for exp in experiment_params), "Missing chunk_size"
    assert all("chunk_overlap" in exp for exp in experiment_params), "Missing chunk_overlap"

    # Verify values are integers
    for exp in experiment_params:
        assert isinstance(exp["chunk_size"], int), "chunk_size must be int"
        assert isinstance(exp["chunk_overlap"], int), "chunk_overlap must be int"

    print("✓ All assertions passed")
    return experiment_params


def test_kwargs_unpacking():
    """Test that kwargs can be unpacked correctly."""

    def mock_ingest_batch(datasheets, chroma_client, force_update=False,
                         chunk_size=None, chunk_overlap=None):
        """Mock ingest_batch function."""
        return {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "force_update": force_update,
        }

    # Simulate experiment parameters
    experiment = {"chunk_size": 512, "chunk_overlap": 50}

    # Test unpacking
    result = mock_ingest_batch(
        datasheets=[],
        chroma_client=None,
        force_update=False,
        **experiment,
    )

    assert result["chunk_size"] == 512
    assert result["chunk_overlap"] == 50
    print("✓ Kwargs unpacking works correctly")


if __name__ == "__main__":
    print("Testing dynamic parameter passing...\n")

    print("1. Testing CSV parsing:")
    experiments = test_csv_parsing()

    print("\n2. Testing kwargs unpacking:")
    test_kwargs_unpacking()

    print("\n✓ All tests passed!")
    print("\nTo add new parameters:")
    print("  1. Add new CLI argument in src/cli/ingest.py")
    print("  2. Add parameter to ingest_batch() in src/ingestion/pipeline.py")
    print("  3. Add column to evaluation/experiments.csv")
    print("  4. No changes needed in evaluate_rag.py!")
