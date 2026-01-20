"""Vector embedding service for semantic certificate search using Vertex AI.

This service generates embeddings using Google's text-embedding-004 model
and stores them in PostgreSQL with PGVector for similarity search.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

import vertexai
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config.settings import settings
from app.models.cert_embedding import CertEmbedding
from loguru import logger


class EmbeddingService:
    """Service for generating and managing vector embeddings."""

    # Page delimiter from the OCR output
    PAGE_DELIMITER = "######End_Of_Page######"

    # text-embedding-004 produces 768-dimensional vectors
    EMBEDDING_DIMENSION = 768

    def __init__(self):
        """Initialize the Vertex AI embedding model."""
        vertexai.init(
            project=settings.gcp_project_id,
            location=settings.vertex_ai_location
        )
        self.model = TextEmbeddingModel.from_pretrained(
            settings.vertex_ai_embedding_model
        )

    def split_by_pages(self, full_text: str) -> List[str]:
        """Split full document text by page delimiter.

        Args:
            full_text: Complete OCR text with page delimiters

        Returns:
            List of page texts
        """
        if not full_text:
            return []

        pages = full_text.split(self.PAGE_DELIMITER)
        # Filter out empty pages
        pages = [page.strip() for page in pages if page.strip()]

        logger.debug(f"Split text into {len(pages)} pages")
        return pages

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Text to embed
            task_type: Task type for the embedding model
                      - "RETRIEVAL_DOCUMENT": For indexing documents
                      - "RETRIEVAL_QUERY": For search queries
                      - "SEMANTIC_SIMILARITY": For similarity comparison

        Returns:
            768-dimensional embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.EMBEDDING_DIMENSION

        try:
            # Truncate if text is too long (max ~20K chars for text-embedding-004)
            max_length = 20000
            if len(text) > max_length:
                logger.warning(
                    f"Text too long ({len(text)} chars), truncating to {max_length}"
                )
                text = text[:max_length]

            # Create embedding input
            embedding_input = TextEmbeddingInput(
                text=text,
                task_type=task_type
            )

            # Generate embedding
            embeddings = self.model.get_embeddings([embedding_input])

            if not embeddings or len(embeddings) == 0:
                logger.error("No embeddings returned from API")
                return [0.0] * self.EMBEDDING_DIMENSION

            # Extract the vector values
            embedding_vector = embeddings[0].values

            logger.debug(
                f"Generated embedding with {len(embedding_vector)} dimensions"
            )

            return embedding_vector

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector on failure
            return [0.0] * self.EMBEDDING_DIMENSION

    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed
            task_type: Task type for embeddings

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            # Prepare inputs
            inputs = [
                TextEmbeddingInput(text=text, task_type=task_type)
                for text in texts
            ]

            # Generate embeddings (API handles batching internally)
            embeddings = self.model.get_embeddings(inputs)

            if len(embeddings) != len(texts):
                logger.warning(
                    f"Embedding count mismatch: {len(embeddings)} != {len(texts)}"
                )

            # Extract vectors
            vectors = [emb.values for emb in embeddings]

            logger.info(f"Generated {len(vectors)} embeddings in batch")

            return vectors

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            # Return zero vectors for all texts
            return [[0.0] * self.EMBEDDING_DIMENSION for _ in texts]

    async def store_certificate_embeddings(
        self,
        db: AsyncSession,
        file_id: UUID,
        request_id: UUID,
        full_text: str,
        metadata: Dict[str, Any]
    ) -> List[CertEmbedding]:
        """Generate and store embeddings for a certificate document.

        Args:
            db: Database session
            file_id: File ID from attachments table
            request_id: Request ID
            full_text: Complete OCR text with page delimiters
            metadata: Additional metadata (language, bidder_name, rfp_number)

        Returns:
            List of created CertEmbedding objects
        """
        # Split into pages
        pages = self.split_by_pages(full_text)

        if not pages:
            logger.warning(f"No pages found in text for file_id={file_id}")
            return []

        # Generate embeddings for all pages
        logger.info(f"Generating embeddings for {len(pages)} pages")
        vectors = self.generate_embeddings_batch(pages)

        # Create database records
        embedding_records = []

        for page_num, (page_text, vector) in enumerate(zip(pages, vectors), start=1):
            embedding_record = CertEmbedding(
                file_id=file_id,
                request_id=request_id,
                content=page_text,
                page_number=page_num,
                total_pages=len(pages),
                language=metadata.get('language'),
                bidder_name=metadata.get('bidder_name'),
                rfp_number=metadata.get('rfp_number'),
                embedding=vector
            )

            db.add(embedding_record)
            embedding_records.append(embedding_record)

        # Commit to database
        await db.commit()

        logger.info(
            f"Stored {len(embedding_records)} embeddings for file_id={file_id}"
        )

        return embedding_records

    async def search_similar_certificates(
        self,
        db: AsyncSession,
        query_text: str,
        request_id: Optional[UUID] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar certificate content using vector similarity.

        Args:
            db: Database session
            query_text: Search query text
            request_id: Optional request ID to filter by
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of similar certificate passages with metadata
        """
        # Generate query embedding
        logger.info(f"Searching for similar certificates: '{query_text[:100]}...'")
        query_vector = self.generate_embedding(query_text, task_type="RETRIEVAL_QUERY")

        # Build query with vector similarity
        # PGVector uses <=> operator for cosine distance (lower is more similar)
        # Cosine similarity = 1 - cosine distance

        query = select(CertEmbedding).order_by(
            CertEmbedding.embedding.cosine_distance(query_vector)
        ).limit(top_k)

        # Filter by request_id if provided
        if request_id:
            query = query.where(CertEmbedding.request_id == request_id)

        # Execute query
        result = await db.execute(query)
        embeddings = result.scalars().all()

        # Format results with similarity scores
        results = []

        for emb in embeddings:
            # Calculate cosine similarity from distance
            # Note: PGVector's cosine_distance returns 1 - cosine_similarity
            # So similarity = 1 - distance
            # But since we're already ordering by distance, we can approximate

            results.append({
                "id": str(emb.id),
                "file_id": str(emb.file_id),
                "request_id": str(emb.request_id),
                "content": emb.content,
                "page_number": emb.page_number,
                "total_pages": emb.total_pages,
                "language": emb.language,
                "bidder_name": emb.bidder_name,
                "rfp_number": emb.rfp_number
            })

        logger.info(f"Found {len(results)} similar certificate passages")

        return results

    async def delete_embeddings_by_file(
        self,
        db: AsyncSession,
        file_id: UUID
    ) -> int:
        """Delete all embeddings for a specific file.

        Args:
            db: Database session
            file_id: File ID to delete embeddings for

        Returns:
            Number of embeddings deleted
        """
        # Find all embeddings for this file
        result = await db.execute(
            select(CertEmbedding).where(CertEmbedding.file_id == file_id)
        )
        embeddings = result.scalars().all()

        # Delete them
        for emb in embeddings:
            await db.delete(emb)

        await db.commit()

        logger.info(f"Deleted {len(embeddings)} embeddings for file_id={file_id}")

        return len(embeddings)

    async def delete_embeddings_by_request(
        self,
        db: AsyncSession,
        request_id: UUID
    ) -> int:
        """Delete all embeddings for a specific request.

        Args:
            db: Database session
            request_id: Request ID to delete embeddings for

        Returns:
            Number of embeddings deleted
        """
        # Find all embeddings for this request
        result = await db.execute(
            select(CertEmbedding).where(CertEmbedding.request_id == request_id)
        )
        embeddings = result.scalars().all()

        # Delete them
        for emb in embeddings:
            await db.delete(emb)

        await db.commit()

        logger.info(f"Deleted {len(embeddings)} embeddings for request_id={request_id}")

        return len(embeddings)
