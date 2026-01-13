"""
ChromaDB client wrapper for datasheet ingestion pipeline.

Provides high-level interface for:
    - Collection initialization
    - Chunk insertion with embeddings
    - Duplicate detection
    - Datasheet deletion
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.collection_configuration import CreateHNSWConfiguration
from chromadb.config import Settings
from chromadb.api import CreateCollectionConfiguration
from chromadb.utils.embedding_functions.openai_embedding_function import (
    OpenAIEmbeddingFunction,
)

from src.models import ContentChunk

logger = logging.getLogger("datasheet_ingestion.chroma_client")


class ChromaDBClient:
    """
    Wrapper for ChromaDB operations in datasheet ingestion pipeline.

    Manages persistent ChromaDB collection with proper metadata schema
    and connection handling.
    """

    DEFAULT_COLLECTION_NAME = "datasheets"
    DEFAULT_CHROMADB_PATH = Path(r"D:\.cache\chromadb")

    def __init__(
        self,
        chromadb_path: Path | None = None,
        collection_name: str | None = None,
    ):
        """
        Initialize ChromaDB client.

        Args:
            chromadb_path: Path to ChromaDB persistent storage
            collection_name: Name of collection to use

        Raises:
            RuntimeError: If ChromaDB initialization fails
        """
        self.chromadb_path = chromadb_path or self.DEFAULT_CHROMADB_PATH
        self.collection_name = collection_name or self.DEFAULT_COLLECTION_NAME

        # Ensure ChromaDB directory exists
        self.chromadb_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.chromadb_path),
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB client initialized at {self.chromadb_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ChromaDB client: {e}") from e

        # Get or create collection
        self.collection = self._initialize_collection()

    def _initialize_collection(self):
        """
        Initialize ChromaDB collection with proper metadata schema.

        Returns:
            ChromaDB collection instance

        Raises:
            RuntimeError: If collection initialization fails
        """
        hnsw_config = CreateHNSWConfiguration(space="cosine")
        ef = OpenAIEmbeddingFunction(model_name="text-embedding-3-small")
        config = CreateCollectionConfiguration(hnsw=hnsw_config, embedding_function=ef)
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                configuration=config,
                embedding_function=ef,
                metadata={
                    "hnsw:space": "cosine",  # Cosine similarity for embeddings
                    "description": "Electrical component datasheets for PCB design",
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dimensions": 1536,
                    "chunking_strategy": "two-stage-semantic",
                    "chunk_size_target": 4000,
                    "chunk_overlap_percent": 15,
                    "schema_version": "1.0.0",
                },
            )

            # Log collection info
            count = collection.count()
            logger.info(
                f"Collection '{self.collection_name}' initialized with {count} existing chunks"
            )

            return collection

        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize collection '{self.collection_name}': {e}"
            ) from e

    def insert_chunks(self, chunks: list[ContentChunk]) -> int:
        """
        Insert content chunks into ChromaDB with embeddings.

        Args:
            chunks: List of content chunks to insert

        Returns:
            Number of chunks successfully inserted

        Raises:
            RuntimeError: If insertion fails
        """
        if not chunks:
            logger.warning("No chunks to insert")
            return 0

        try:
            # Convert chunks to ChromaDB format
            documents = []
            metadatas = []
            ids = []

            for chunk in chunks:
                text, metadata = chunk.to_chromadb_format()
                documents.append(text)
                metadatas.append(metadata)

                # Generate ID: datasheet_name + chunk_index
                chunk_id = f"{chunk.datasheet_name}_{chunk.chunk_index}"
                ids.append(chunk_id)

            # Insert into ChromaDB (embeddings auto-generated)
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

            logger.info(f"Successfully inserted {len(chunks)} chunks into ChromaDB")
            return len(chunks)

        except Exception as e:
            raise RuntimeError(f"Failed to insert chunks into ChromaDB: {e}") from e

    def datasheet_exists(self, datasheet_name: str) -> bool:
        """
        Check if datasheet already exists in ChromaDB.

        Args:
            datasheet_name: Name of datasheet to check

        Returns:
            True if datasheet exists, False otherwise
        """
        try:
            results = self.collection.get(
                where={"datasheet_name": datasheet_name},
                limit=1,
            )

            exists = len(results["ids"]) > 0
            if exists:
                logger.debug(f"Datasheet '{datasheet_name}' already exists in ChromaDB")
            return exists

        except Exception as e:
            logger.error(f"Error checking datasheet existence: {e}")
            return False

    def delete_datasheet(self, datasheet_name: str) -> int:
        """
        Delete all chunks for a specific datasheet.

        Args:
            datasheet_name: Name of datasheet to delete

        Returns:
            Number of chunks deleted

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            # Get all chunks for this datasheet
            results = self.collection.get(where={"datasheet_name": datasheet_name})

            chunk_ids = results["ids"]
            if not chunk_ids:
                logger.debug(f"No chunks found for datasheet '{datasheet_name}'")
                return 0

            # Delete chunks
            self.collection.delete(ids=chunk_ids)

            logger.info(
                f"Deleted {len(chunk_ids)} chunks for datasheet '{datasheet_name}'"
            )
            return len(chunk_ids)

        except Exception as e:
            raise RuntimeError(
                f"Failed to delete datasheet '{datasheet_name}': {e}"
            ) from e

    def get_collection_info(self) -> dict[str, Any]:
        """
        Get collection metadata and statistics.

        Returns:
            Dictionary with collection information
        """
        try:
            count = self.collection.count()
            metadata = self.collection.metadata

            return {
                "name": self.collection_name,
                "path": str(self.chromadb_path),
                "count": count,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {
                "name": self.collection_name,
                "path": str(self.chromadb_path),
                "error": str(e),
            }

    def validate_connection(self) -> tuple[bool, str | None]:
        """
        Validate ChromaDB connection and permissions.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check path accessibility
        if not self.chromadb_path.exists():
            return False, f"ChromaDB path does not exist: {self.chromadb_path}"

        if not self.chromadb_path.is_dir():
            return False, f"ChromaDB path is not a directory: {self.chromadb_path}"

        # Check write permissions
        try:
            test_file = self.chromadb_path / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return False, f"Permission denied: cannot write to {self.chromadb_path}"
        except OSError as e:
            return False, f"Error accessing ChromaDB path: {e}"

        # Check collection accessibility
        try:
            self.collection.count()
        except Exception as e:
            return False, f"Cannot access collection '{self.collection_name}': {e}"

        return True, None
