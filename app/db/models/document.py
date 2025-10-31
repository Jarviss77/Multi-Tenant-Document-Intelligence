from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    chunking_strategy = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant = relationship("Tenant", back_populates="documents")
    embedding_jobs = relationship("EmbeddingJob", back_populates="document")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
