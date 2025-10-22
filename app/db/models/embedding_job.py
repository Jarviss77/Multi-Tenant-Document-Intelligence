from sqlalchemy import Column, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from app.db.base import Base
import enum, uuid

class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"))
    status = Column(Enum(JobStatus), default=JobStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
