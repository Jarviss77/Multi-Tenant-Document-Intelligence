from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    size = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    chunk_metadata = Column(JSON, nullable=True)  # Store additional chunk metadata
    embedding_id = Column(String, nullable=True)  # Links to vector store
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")
    tenant = relationship("Tenant", back_populates="chunks")
    embedding_jobs = relationship("EmbeddingJob", back_populates="chunk")
    
    # Composite index for common query pattern: tenant_id + document_id
    __table_args__ = (
        Index('idx_chunks_tenant_document', 'tenant_id', 'document_id'),
    )
