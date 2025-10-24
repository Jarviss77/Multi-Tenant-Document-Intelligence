from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from app.services.storage_service import StorageService
from app.core.auth import get_tenant_from_api_key
from app.core.rate_limiter import rate_limit_dependency
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.db.models.document import Document
from app.workers.queue_config import KafkaProducerService
from app.db.sessions import get_db
from app.utils.logger import get_logger, log_database_operation, log_kafka_message
import os
import uuid
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

storage_service = StorageService()

@router.post("", dependencies=[Depends(rate_limit_dependency(action="uploads", max_requests=settings.UPLOADS_PER_MINUTE, window_seconds=60))])
async def upload_file(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db)):

    # Save file to storage
    logger.info(f"Uploading file '{file.filename}' for tenant {tenant.id}")
    file_path = await storage_service.save_file(tenant.id, file)
    logger.info(f"File saved to: {file_path}")

    # Create Document record
    document_id = str(uuid.uuid4())
    document = Document(
        id=document_id,
        tenant_id=tenant.id,
        title=file.filename or "Untitled",
        content="",  # Will be populated by the worker after processing
        created_at=datetime.utcnow(),
    )
    db.add(document)
    log_database_operation(logger, "INSERT", "documents", document_id)
    await db.commit()
    await db.refresh(document)
    logger.info(f"Created document record: {document_id}")

    # Create EmbeddingJob record
    job_id = str(uuid.uuid4())
    job = EmbeddingJob(
        id=job_id,
        document_id=document.id,
        tenant_id=tenant.id,
        status=JobStatus.pending,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    log_database_operation(logger, "INSERT", "embedding_jobs", job_id)
    await db.commit()
    await db.refresh(job)
    logger.info(f"Created embedding job: {job_id}")

    # Publish job to Kafka for async ingestion
    try:
        producer = KafkaProducerService()
        await producer.start()
        job_data = {
            "job_id": job.id,
            "tenant_id": tenant.id,
            "document_id": document.id,
            "file_path": file_path,
        }

        log_kafka_message(logger, "PUBLISH", "document-intelligence", job.id)

        await producer.publish_job(job_data)
        await producer.stop()

        logger.info(f"Successfully published job {job.id} to Kafka")

    except Exception as e:
        logger.error(f"Error publishing to Kafka: {e}")
        # Don't fail the upload if Kafka is down

    # Respond to client immediately
    return {
        "message": "File uploaded successfully and ingestion started",
        "file_path": file_path,
        "document_id": document.id,
        "job_id": job.id,
    }



@router.get("/get", response_model=List[str])
async def list_uploaded_files(tenant=Depends(get_tenant_from_api_key)):
    tenant_dir = os.path.join("uploads", tenant.id)
    if not os.path.exists(tenant_dir):
        return []
    return os.listdir(tenant_dir)


@router.delete("/{filename}")
async def delete_file(filename: str, tenant=Depends(get_tenant_from_api_key)):
    """Delete a file belonging to the tenant."""
    success = storage_service.delete_file(tenant.id, filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"message": f"{filename} deleted successfully"}
