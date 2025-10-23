# from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from app.db.sessions import get_db
# from app.db.models.document import Document
# from app.core.auth import get_tenant_from_api_key
# from app.services.text_pipeline import TextDocumentPipeline
# from app.schemas.kafka_events import TextContentType
# from pydantic import BaseModel, ConfigDict
# import uuid
# import logging
# from fastapi import APIRouter
#
# logger = logging.getLogger(__name__)
#
# router = APIRouter()
#
# class DocumentCreate(BaseModel):
#     title: str
#     content: str
#
# class DocumentIngestionResponse(BaseModel):
#     document_id: str
#     event_id: str
#     status: str
#     message: str
#
# @router.post("/", response_model=DocumentIngestionResponse)
# async def ingest_document(
#     payload: DocumentCreate,
#     background_tasks: BackgroundTasks,
#     tenant=Depends(get_tenant_from_api_key),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Ingest document for vector processing (async through Kafka)"""
#     try:
#         # First, store in database
#         document = Document(
#             id=str(uuid.uuid4()),
#             tenant_id=tenant.id,
#             title=payload.title,
#             content=payload.content,
#         )
#
#         db.add(document)
#         await db.commit()
#         await db.refresh(document)
#
#         # Then, queue for vector processing
#         event_id = await text_pipeline.ingest_text_document(
#             content=payload.content,
#             content_type=payload.content_type,
#             tenant_id=tenant.id,
#             document_id=document.id,
#             metadata={
#                 "title": payload.title,
#                 "db_document_id": document.id
#             }
#         )
#
#         return DocumentIngestionResponse(
#             document_id=document.id,
#             event_id=event_id,
#             status="queued",
#             message="Document queued for vector processing"
#         )
#
#     except Exception as e:
#         logger.error(f"Failed to ingest document: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")