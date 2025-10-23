from fastapi import APIRouter
from app.api.v1.routes import tenants, health, documents, uploads

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
# api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])