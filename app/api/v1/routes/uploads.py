from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from app.services.storage_service import StorageService
from app.core.auth import get_tenant_from_api_key
from app.core.rate_limiter import rate_limit_dependency
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.embedding_job import EmbeddingJob, JobStatus
from app.workers.queue_config import KafkaProducerService
from app.db.sessions import get_db
import os
import uuid
from datetime import datetime

router = APIRouter()

storage_service = StorageService()

@router.post("/", dependencies=[Depends(rate_limit_dependency(action="uploads", max_requests=settings.UPLOADS_PER_MINUTE, window_seconds=60))])
async def upload_file(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db)):

    file_path = await storage_service.save_file(tenant.id, file)

    job_id = str(uuid.uuid4())
    job = EmbeddingJob(
        id=job_id,
        tenant_id=tenant.id,
        status=JobStatus.pending,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 3️⃣ Publish job to Kafka for async ingestion
    producer = KafkaProducerService()
    await producer.start()
    await producer.publish_job(
        {
            "job_id": job.id,
            "tenant_id": tenant.id,
        }
    )
    await producer.stop()

    # 4️⃣ Respond to client immediately
    return {
        "message": "File uploaded successfully and ingestion started",
        "file_path": file_path,
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
