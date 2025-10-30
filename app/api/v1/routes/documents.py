from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.sessions import get_db
from app.db.models.document import Document
from app.db.models.chunks import Chunk
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.core.auth import get_tenant_from_api_key
from app.services.storage_service import StorageService
from app.utils.dto.document import DocumentCreate, DocumentResponse
from app.services.chunking_service import ChunkingService
from app.services.vector_store import PineconeVectorStore
from app.utils.read_file import extract_text
from app.workers.v2.producer import KafkaProducerService
from app.utils.logger import get_logger, log_database_operation, log_kafka_message
import uuid
from sqlalchemy import delete
from datetime import datetime, timezone
from app.core.config import settings

logger = get_logger(__name__)

router = APIRouter()
storage_service = StorageService()

@router.post("/", response_model=DocumentResponse)
async def upload_document(payload: DocumentCreate, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    document = Document(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        title=payload.title,
        content=payload.content,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    tenant=Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db)
):
    """List all documents for the current tenant."""
    result = await db.execute(
        select(Document).where(Document.tenant_id == tenant.id)
    )
    docs = result.scalars().all()
    return docs

@router.patch("/update/{document_id}")
async def update_document(
    document_id: str = Path(..., description="ID of the document to update"),
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db)
):
    # Load document and validate ownership
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant.id
        )
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info(f"Uploading file '{file.filename}' for tenant {tenant.id}")
    file_path = await storage_service.save_file(tenant.id, file)
    logger.info(f"File saved to: {file_path}")

    # Read new content from uploaded file
    try:
        logger.info(f"Extracting text from file: {file_path}")
        new_content = await extract_text(file_path)
        logger.info(f"Extracted {len(file_path)} characters from file")
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    # Update document fields
    document.title = file.filename or document.title
    document.content = new_content
    document.chunking_strategy = document.chunking_strategy or "fixed_size"

    # Delete existing chunks from DB
    await db.execute(
        delete(Chunk).where(
            Chunk.document_id == document.id,
            Chunk.tenant_id == tenant.id
        )
    )

    # Delete existing embeddings from vector store
    vector_store = PineconeVectorStore()
    for chunk in await ChunkingService(db).get_document_chunks(document.id, tenant.id):
        try:
            await vector_store.delete_document_vector(tenant.id, chunk.id)
            logger.info(f"Deleted embedding for chunk {chunk.id} from vector store")
        except Exception as e:
            logger.error(f"Failed to delete embedding for chunk {chunk.id}: {e}")

    # delete all chunks from DB
    await db.execute(
        delete(Chunk).where(
            Chunk.document_id == document.id,
            Chunk.tenant_id == tenant.id
        )
    )

    # Commit document update and chunk deletions
    await db.commit()
    await db.refresh(document)

    # Recreate chunks for updated content
    chunking_service = ChunkingService(db)
    await chunking_service.create_chunks(
        content=new_content,
        document_id=document.id,
        tenant_id=tenant.id,
        strategy=settings.CHUNKING_STRATEGY,
    )

    # Fetch new chunks
    chunks_result = await db.execute(
        select(Chunk).where(
            Chunk.document_id == document.id,
            Chunk.tenant_id == tenant.id,
        ).order_by(Chunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    # Create embedding jobs for each new chunk and publish to Kafka
    embedding_jobs = []
    producer = KafkaProducerService()
    try:
        await producer.start()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Kafka producer unavailable")
    try:
        for chunk in chunks:
            # Create EmbeddingJob record for each chunk
            job_id = str(uuid.uuid4())
            job = EmbeddingJob(
                id=job_id,
                document_id=document.id,
                tenant_id=tenant.id,
                chunk_id=chunk.id,
                status=JobStatus.pending,
                created_at=datetime.now(timezone.utc)
            )
            logger.info(f"Created job record: {job_id}")
            db.add(job)
            embedding_jobs.append((job, chunk))

        await db.commit()
        await db.refresh(document)
        log_database_operation(logger, "INSERT", "embedding_jobs", job_id)

        # Publish job to Kafka for async processing
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
            logger.info(f"Published embedding job {job.id} for chunk {chunk.id}")

        logger.info(f"Created {len(embedding_jobs)} embedding jobs")

    except Exception as e:
        logger.error(f"Error creating embedding jobs or publishing to Kafka: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process document chunks")

    finally:
        await producer.stop()

    # Respond to client immediately
    return {
        "message": "File updated successfully and chunking completed",
        "updated_file_path": file_path,
        "document_id": document.id,
        "chunks_created": len(chunks),
        "embedding_jobs_queued": len(embedding_jobs),
        "chunking_strategy": settings.CHUNKING_STRATEGY,
        "tenant_id": tenant.id,
        "first-5_chunks": [chunk.content for chunk in chunks[:5]]
    }