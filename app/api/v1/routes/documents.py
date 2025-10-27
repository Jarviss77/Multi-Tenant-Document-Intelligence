from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.sessions import get_db
from app.db.models.document import Document
from app.core.auth import get_tenant_from_api_key
from app.utils.dto.document import DocumentCreate, DocumentResponse
import uuid

router = APIRouter()

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