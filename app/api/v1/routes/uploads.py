from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from app.services.storage_service import StorageService
from app.services.chunking_service import ChunkingService
from app.core.auth import get_tenant_from_api_key
from app.core.rate_limiter import rate_limit_dependency
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.db.models.document import Document
from app.db.models.chunks import Chunk
from app.workers.v2.producer import KafkaProducerService
from app.db.sessions import get_db
from app.utils.logger import get_logger, log_database_operation, log_kafka_message
from app.utils.read_file import extract_text
from sqlalchemy import select
import os
import uuid
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

storage_service = StorageService()


@router.post("/", dependencies=[Depends(rate_limit_dependency(action="uploads", max_requests=settings.UPLOADS_PER_MINUTE, window_seconds=60))])
async def upload_file(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db)):

    # Save file to storage
    logger.info(f"Uploading file '{file.filename}' for tenant {tenant.id}")
    file_path = await storage_service.save_file(tenant.id, file)
    logger.info(f"File saved to: {file_path}")

    # Extract text content from the file
    logger.info(f"Extracting text from file: {file_path}")
    text_content = await extract_text(file_path)
    logger.info(f"Extracted {len(text_content)} characters from file")

    # Create Document record
    document_id = str(uuid.uuid4())
    document = Document(
        id=document_id,
        tenant_id=tenant.id,
        title=file.filename,
        content=text_content,
        file_path=file_path,
        chunking_strategy=settings.CHUNKING_STRATEGY,
        created_at=datetime.utcnow(),
    )
    db.add(document)
    log_database_operation(logger, "INSERT", "documents", document_id)
    await db.commit()
    await db.refresh(document)
    logger.info(f"Created document record: {document_id}")

    chunking_service = ChunkingService(db)

    await chunking_service.create_chunks(
        content=text_content,
        document_id=document_id,
        tenant_id=tenant.id,
        strategy=settings.CHUNKING_STRATEGY,
    )

    # Retrieve created chunks
    chunks = await db.execute(
        select(Chunk).where(
            Chunk.document_id == document.id,
            Chunk.tenant_id == tenant.id,
        ).order_by(Chunk.chunk_index)
    )
    chunks = chunks.scalars().all()

    # Create embedding jobs for each chunk
    embedding_jobs = []
    producer = KafkaProducerService()
    try:
        await producer.start()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Kafka producer unavailable")
    
    try:
        # Create all EmbeddingJob records for bulk insert
        jobs_to_add = []
        for chunk in chunks:
            job_id = str(uuid.uuid4())
            job = EmbeddingJob(
                id=job_id,
                document_id=document.id,
                tenant_id=tenant.id,
                chunk_id=chunk.id,
                status=JobStatus.pending,
                created_at=datetime.utcnow(),
            )
            jobs_to_add.append(job)
            embedding_jobs.append((job, chunk))

        # Bulk insert all embedding jobs at once
        db.add_all(jobs_to_add)
        await db.commit()
        await db.refresh(document)
        log_database_operation(logger, "BULK_INSERT", "embedding_jobs", f"{len(jobs_to_add)}_jobs")

        # Publish jobs to Kafka for async processing
        for job, chunk in embedding_jobs:
            job_data = {
                "job_id": job.id,
                "tenant_id": tenant.id,
                "document_id": document.id,
                "chunk_id": chunk.id,
                "chunk_content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "chunk_size": chunk.size,
                "chunk_metadata": chunk.chunk_metadata,
                "file_path": file_path,
            }

            log_kafka_message(logger, "PUBLISH", "document-intelligence", job.id)
            await producer.publish_job(job_data)

        logger.info(f"Created and published {len(embedding_jobs)} embedding jobs")

    except Exception as e:
        logger.error(f"Error creating embedding jobs or publishing to Kafka: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process document chunks")
    
    finally:
        await producer.stop()

    # Respond to client immediately
    return {
        "message": "File uploaded successfully and chunking completed",
        "file_path": file_path,
        "document_id": document.id,
        "chunks_created": len(chunks),
        "embedding_jobs_queued": len(embedding_jobs),
        "chunking_strategy": settings.CHUNKING_STRATEGY,
        "tenant_id": tenant.id,
        "first-5_chunks": [chunk.content for chunk in chunks[:5]]
    }



@router.get("/get", response_model=List[str])
async def list_uploaded_files(tenant=Depends(get_tenant_from_api_key)):
    tenant_dir = os.path.join("uploads", tenant.id)
    if not os.path.exists(tenant_dir):
        return []
    return os.listdir(tenant_dir)
