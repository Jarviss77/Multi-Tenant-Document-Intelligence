import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.chunks import Chunk
from app.db.models.document import Document
from sqlalchemy import select
from datetime import datetime
from app.utils.chunking import chunking_strategy
from app.utils.logger import get_logger, log_database_operation

logger = get_logger("services.chunking_service")

class ChunkingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_chunks(self, tenant_id: str, document_id: str, content: str, strategy: str) -> Document:
        # get the document from the uploads folder
        document = await self.db.get(Document, document_id)

        if not document or document.tenant_id != tenant_id:
            raise ValueError("Document not found or access denied")

        chunks_data = chunking_strategy.chunk_document(text=content, strategy=strategy)

        # Prepare all chunks for bulk insert - more efficient than individual inserts
        chunks_to_add = []
        for i, chunk_data in enumerate(chunks_data):
            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                tenant_id=tenant_id,
                content=chunk_data.get("text"),
                chunk_index=i,
                start_char=chunk_data.get('start_char'),
                end_char=chunk_data.get('end_char'),
                size=chunks_data[i]['chunk_size'],
                created_at=datetime.utcnow(),
            )
            chunks_to_add.append(chunk)

        # Bulk insert all chunks at once
        self.db.add_all(chunks_to_add)
        await self.db.commit()
        
        if chunks_to_add:
            log_database_operation(logger, "BULK_INSERT", "document_chunks", f"{len(chunks_to_add)}_chunks")
        logger.info(f"Saved {len(chunks_data)} chunks to database")

        await self.db.refresh(document)
        return document

    async def get_document_chunks(
        self,
        document_id: str,
        tenant_id: str
    ) -> list[Chunk]:
        """Get all chunks for a document."""
        result = await self.db.execute(
            select(Chunk).where(
                Chunk.document_id == document_id,
                Chunk.tenant_id == tenant_id
            ).order_by(Chunk.chunk_index)
        )
        return result.scalars().all()

    async def search_chunks(
            self,
            tenant_id: str,
            query: str = None,
            document_id: str = None,
            limit: int = 10
    ) -> list[Chunk]:
        """Search chunks by content (simple text search)."""
        stmt = select(Chunk).where(
            Chunk.tenant_id == tenant_id
        )

        if query:
            stmt = stmt.where(Chunk.content.ilike(f"%{query}%"))

        if document_id:
            stmt = stmt.where(Chunk.document_id == document_id)

        stmt = stmt.order_by(Chunk.chunk_index).limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()