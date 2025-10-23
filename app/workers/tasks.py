# app/workers/tasks.py
import aiofiles
from datetime import datetime
import logging
from sqlalchemy.future import select
from app.services.embedding_service import GeminiEmbeddingService
from app.services.vector_store import PineconeVectorStore
from app.db.sessions import AsyncSessionLocal
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.utils.read_file import extract_text

logger = logging.getLogger("workers.tasks")

embedding_service = GeminiEmbeddingService()
vector_store = PineconeVectorStore()


async def extract_text(file_path: str) -> str:
    """Reads file contents asynchronously."""
    async with aiofiles.open(file_path, "r") as f:
        return await f.read()


async def process_ingestion_job(job_data: dict):
    """Main Kafka message handler for ingestion jobs."""
    job_id = job_data.get("job_id")
    tenant_id = job_data.get("tenant_id")
    file_path = job_data.get("file_path")

    logger.info(f"Processing ingestion job {job_id} for tenant {tenant_id}")

    async with AsyncSessionLocal() as db:
        # Fetch job
        result = await db.execute(select(EmbeddingJob).where(EmbeddingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.warning(f"Job {job_id} not found in database.")
            return

        job.status = JobStatus.processing
        await db.commit()

        try:
            # Extract text and embed
            text = await extract_text(file_path)
            embedding = await embedding_service.embed_text(text)

            # Store in Pinecone
            vector_store.upsert_vector(
                tenant_id=tenant_id,
                doc_id=job.id,
                embedding=embedding,
                metadata={"file_path": file_path},
            )

            # Mark as complete
            job.status = JobStatus.completed
            job.error_message = None
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            job.status = JobStatus.failed
            job.error_message = str(e)
            logger.exception(f"Job {job_id} failed: {e}")

        job.updated_at = datetime.utcnow()
        await db.commit()
