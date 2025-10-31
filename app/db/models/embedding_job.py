from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, Index
from sqlalchemy.sql import func
from app.db.base import Base
import enum, uuid
from sqlalchemy.orm import relationship

class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    chunk_id = Column(String, ForeignKey("chunks.id", ondelete="CASCADE"), index=True)

    status = Column(Enum(JobStatus), default=JobStatus.pending, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    error_message = Column(String, nullable=True)  # Add error_message column for task processor

    tenant = relationship("Tenant", back_populates="embedding_jobs")
    document = relationship("Document", back_populates="embedding_jobs")
    chunk = relationship("Chunk", back_populates="embedding_jobs")
    
    # Composite index for common query pattern: tenant_id + status
    __table_args__ = (
        Index('idx_embedding_jobs_tenant_status', 'tenant_id', 'status'),
    )