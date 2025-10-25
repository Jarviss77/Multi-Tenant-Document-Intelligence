import aiofiles
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.services.embedding_service import GeminiEmbeddingService
from app.services.vector_store import PineconeVectorStore
from app.db.sessions import AsyncSessionLocal
from app.db.base import load_all_models
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.db.models.document import Document
from app.db.models.chunks import Chunk
from app.utils.logger import get_logger, log_embedding_operation, log_database_operation

load_all_models()

logger = get_logger("workers.tasks")

embedding_service = GeminiEmbeddingService()
vector_store = PineconeVectorStore()


async def process_ingestion_job(job_data: dict):
    """Main Kafka message handler for chunk embedding jobs."""
    job_id = job_data.get("job_id")
    tenant_id = job_data.get("tenant_id")
    document_id = job_data.get("document_id")
    chunk_id = job_data.get("chunk_id")
    chunk_content = job_data.get("chunk_content")
    chunk_index = job_data.get("chunk_index")
    chunk_size = job_data.get("chunk_size")
    file_path = job_data.get("file_path")

    logger.info(f"Processing chunk embedding job {job_id} for tenant {tenant_id}, document {document_id}, chunk {chunk_id}")
    logger.debug(f"Job data received: {job_data}")
    
    # Check if we have the required fields
    if not chunk_content:
        logger.error(f"Missing chunk_content in job data for job {job_id}. Skipping processing.")
        return
    
    if not chunk_id:
        logger.error(f"Missing chunk_id in job data for job {job_id}. Skipping processing.")
        return

    async with AsyncSessionLocal() as db:
        try:
            # Fetch job
            log_database_operation(logger, "SELECT", "embedding_jobs", job_id)
            result = await db.execute(
                select(EmbeddingJob)
                .where(EmbeddingJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"Job {job_id} not found in database.")
                return

            job.status = JobStatus.processing
            job.updated_at = datetime.utcnow()
            log_database_operation(logger, "UPDATE", "embedding_jobs", job_id)
            await db.commit()

            try:
                # Generate embedding for the chunk
                log_embedding_operation(logger, "GENERATE", chunk_id, tenant_id)
                embedding = await embedding_service.embed_text(chunk_content)
                logger.info(f"Generated embedding with {len(embedding)} dimensions for chunk {chunk_id}")

                # Store in vector database with chunk-specific metadata
                log_embedding_operation(logger, "STORE", chunk_id, tenant_id)
                await vector_store.upsert_vector(
                    tenant_id=tenant_id,
                    doc_id=chunk_id,  # Use chunk_id as the unique identifier
                    embedding=embedding,
                    metadata={
                        "file_path": file_path,
                        "document_id": document_id,
                        "chunk_id": chunk_id,
                        "tenant_id": tenant_id,
                        "job_id": job_id,
                        "chunk_index": chunk_index,
                        "chunk_size": chunk_size,
                        "content_length": len(chunk_content)
                    },
                )
                logger.info(f"Successfully stored chunk embedding in vector database")

                # Update chunk with embedding_id
                log_database_operation(logger, "SELECT", "document_chunks", chunk_id)
                chunk_result = await db.execute(
                    select(Chunk).where(Chunk.id == chunk_id)
                )
                chunk = chunk_result.scalar_one_or_none()
                if chunk:
                    chunk.embedding_id = chunk_id  # Use chunk_id as embedding_id
                    log_database_operation(logger, "UPDATE", "document_chunks", chunk.id)
                    logger.info(f"Updated chunk {chunk.id} with embedding_id")

                # Mark job as complete
                job.status = JobStatus.completed
                job.error_message = None
                log_database_operation(logger, "UPDATE", "embedding_jobs", job_id)
                logger.info(f"Chunk embedding job {job_id} completed successfully")

            except Exception as e:
                job.status = JobStatus.failed
                job.error_message = str(e)
                logger.exception(f"Chunk embedding job {job_id} failed: {e}")

            job.updated_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Database error processing chunk job {job_id}: {e}")
            await db.rollback()