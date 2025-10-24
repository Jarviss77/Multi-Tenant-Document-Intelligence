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
from app.utils.logger import get_logger, log_embedding_operation, log_database_operation

load_all_models()

logger = get_logger("workers.tasks")

embedding_service = GeminiEmbeddingService()
vector_store = PineconeVectorStore()


async def process_ingestion_job(job_data: dict):
    """Main Kafka message handler for ingestion jobs."""
    job_id = job_data.get("job_id")
    tenant_id = job_data.get("tenant_id")
    document_id = job_data.get("document_id")
    file_path = job_data.get("file_path")

    logger.info(f"Processing ingestion job {job_id} for tenant {tenant_id}, document {document_id}")
    logger.debug(f"Job data received: {job_data}")
    
    # Check if we have the required fields
    if not file_path:
        logger.error(f"Missing file_path in job data for job {job_id}. Skipping processing.")
        return
    
    if not document_id:
        logger.error(f"Missing document_id in job data for job {job_id}. Skipping processing.")
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
                # Extract text - using your existing extract_text utility
                logger.info(f"Extracting text from file: {file_path}")
                from app.utils.read_file import extract_text as extract_text_util
                text = await extract_text_util(file_path)
                logger.info(f"Extracted {len(text)} characters from file")

                # Generate embedding
                log_embedding_operation(logger, "GENERATE", job.document_id, tenant_id)
                embedding = await embedding_service.embed_text(text)
                logger.info(f"Generated embedding with {len(embedding)} dimensions")

                # Store in vector database
                log_embedding_operation(logger, "STORE", job.document_id, tenant_id)
                await vector_store.upsert_vector(
                    tenant_id=tenant_id,
                    doc_id=job.document_id,
                    embedding=embedding,
                    metadata={
                        "file_path": file_path,
                        "document_id": job.document_id,
                        "tenant_id": tenant_id,
                        "job_id": job_id
                    },
                )
                logger.info(f"Successfully stored embedding in vector database")

                # Update document with extracted content
                log_database_operation(logger, "SELECT", "documents", job.document_id)
                document_result = await db.execute(
                    select(Document).where(Document.id == job.document_id)
                )
                document = document_result.scalar_one_or_none()
                if document:
                    document.content = text
                    document.embedding_id = job.document_id  # Use document_id as embedding_id for now
                    log_database_operation(logger, "UPDATE", "documents", document.id)
                    logger.info(f"Updated document {document.id} with extracted content")

                # Mark job as complete
                job.status = JobStatus.completed
                job.error_message = None
                log_database_operation(logger, "UPDATE", "embedding_jobs", job_id)
                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                job.status = JobStatus.failed
                job.error_message = str(e)
                logger.exception(f"Job {job_id} failed: {e}")

            job.updated_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Database error processing job {job_id}: {e}")
            await db.rollback()