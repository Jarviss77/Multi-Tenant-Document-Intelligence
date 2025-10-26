import aiofiles
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.services.embedding_service import GeminiEmbeddingService
from app.services.vector_store import PineconeVectorStore
from app.db.sessions import AsyncSessionLocal
from app.db.base import load_all_models
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.db.models.document import Document
from app.db.models.chunks import Chunk
from app.utils.logger import get_logger, log_embedding_operation, log_database_operation
import asyncio

load_all_models()

logger = get_logger("workers.v2.tasks")

embedding_service = GeminiEmbeddingService()
vector_store = PineconeVectorStore()


class TaskProcessor:
    """Enhanced task processor with robust error handling and monitoring"""

    def __init__(self):
        self._processed_count = 0
        self._failed_count = 0
        self._last_error = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((OperationalError, ConnectionError))
    )
    async def _update_job_status(self, db, job_id: str, status: JobStatus, error_message: str = None):
        """Update job status with retry logic"""
        try:
            log_database_operation(logger, "SELECT", "embedding_jobs", job_id)
            result = await db.execute(
                select(EmbeddingJob)
                .where(EmbeddingJob.id == job_id)
                .with_for_update()  # Lock the row for update
            )
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"Job {job_id} not found in DB")
                return None

            job.status = status
            job.updated_at = datetime.utcnow()
            if error_message:
                job.error_message = error_message[:500]  # Limit error message length

            log_database_operation(logger, "UPDATE", "embedding_jobs", job_id)
            await db.commit()

            return job

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Database error updating job {job_id}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def _generate_embedding(self, chunk_content: str, chunk_id: str, tenant_id: str):
        """Generate embedding with retry logic"""
        try:
            log_embedding_operation(logger, "GENERATE", chunk_id, tenant_id)
            embedding = await embedding_service.embed_text(chunk_content)

            if not embedding or len(embedding) == 0:
                raise ValueError("Empty embedding generated")

            logger.info(f"enerated embedding with {len(embedding)} dimensions for chunk {chunk_id}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for chunk {chunk_id}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def _store_embedding(self, tenant_id: str, chunk_id: str, embedding: list, metadata: Dict[str, Any]):
        """Store embedding in vector store with retry logic"""
        try:
            log_embedding_operation(logger, "STORE", chunk_id, tenant_id)
            await vector_store.upsert_vector(
                tenant_id=tenant_id,
                doc_id=chunk_id,
                embedding=embedding,
                metadata=metadata,
            )
            logger.info(f"Successfully stored embedding for chunk {chunk_id}")

        except Exception as e:
            logger.error(f"Failed to store embedding for chunk {chunk_id}: {e}")
            raise

    async def _validate_job_data(self, job_data: dict) -> bool:
        """Validate job data before processing"""
        required_fields = ['job_id', 'tenant_id', 'document_id', 'chunk_id', 'chunk_content']

        for field in required_fields:
            if field not in job_data or not job_data[field]:
                logger.error(f"Missing or empty required field: {field} in job {job_data.get('job_id')}")
                return False

        if len(job_data['chunk_content']) > 10000:  # Reasonable content length limit
            logger.warning(
                f"Chunk content too long ({len(job_data['chunk_content'])} chars) for job {job_data['job_id']}")

        return True

    async def process_ingestion_job(self, job_data: dict):
        """Enhanced main Kafka message handler for chunk embedding jobs."""
        job_id = job_data.get("job_id")
        tenant_id = job_data.get("tenant_id")
        document_id = job_data.get("document_id")
        chunk_id = job_data.get("chunk_id")
        chunk_content = job_data.get("chunk_content")
        chunk_index = job_data.get("chunk_index")
        chunk_size = job_data.get("chunk_size")
        file_path = job_data.get("file_path")

        logger.info(f"🔨 Processing chunk embedding job {job_id} for tenant {tenant_id}, "
                    f"document {document_id}, chunk {chunk_id}")

        # Validate job data
        if not await self._validate_job_data(job_data):
            self._failed_count += 1
            return

        async with AsyncSessionLocal() as db:
            try:
                # Update job status to processing
                job = await self._update_job_status(db, job_id, JobStatus.processing)
                if not job:
                    self._failed_count += 1
                    return

                # Generate embedding
                embedding = await self._generate_embedding(chunk_content, chunk_id, tenant_id)

                # Prepare metadata for vector store
                metadata = {
                    "file_path": file_path,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "tenant_id": tenant_id,
                    "job_id": job_id,
                    "chunk_index": chunk_index,
                    "chunk_size": chunk_size,
                    "content_length": len(chunk_content),
                    "processed_at": datetime.utcnow().isoformat()
                }

                # Store in vector database
                await self._store_embedding(tenant_id, chunk_id, embedding, metadata)

                # Update chunk with embedding_id
                try:
                    log_database_operation(logger, "SELECT", "document_chunks", chunk_id)
                    chunk_result = await db.execute(
                        select(Chunk).where(Chunk.id == chunk_id)
                    )
                    chunk = chunk_result.scalar_one_or_none()

                    if chunk:
                        chunk.embedding_id = chunk_id
                        log_database_operation(logger, "UPDATE", "document_chunks", chunk.id)
                        logger.info(f"Updated chunk {chunk.id} with embedding_id")
                    else:
                        logger.warning(f"Chunk {chunk_id} not found in database")

                except SQLAlchemyError as e:
                    logger.error(f"Failed to update chunk {chunk_id}: {e}")
                    # Don't fail the entire job if chunk update fails

                # Mark job as complete
                await self._update_job_status(db, job_id, JobStatus.completed)
                self._processed_count += 1

                logger.info(f"🎉 Chunk embedding job {job_id} completed successfully")

            except Exception as e:
                self._failed_count += 1
                self._last_error = str(e)

                try:
                    # Update job status to failed
                    await self._update_job_status(db, job_id, JobStatus.failed, str(e))
                    logger.exception(f"Chunk embedding job {job_id} failed: {e}")
                except Exception as db_error:
                    logger.error(f"Failed to update job status for {job_id}: {db_error}")

    def get_stats(self) -> Dict[str, Any]:
        total = self._processed_count + self._failed_count
        success_rate = (self._processed_count / total * 100) if total > 0 else 0

        return {
            "processed_jobs": self._processed_count,
            "failed_jobs": self._failed_count,
            "success_rate": round(success_rate, 1),
            "last_error": self._last_error
        }


# Global task processor instance
task_processor = TaskProcessor()


async def process_ingestion_job(job_data: dict):
    await task_processor.process_ingestion_job(job_data)