from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

@router.get("/", summary="Health check")
async def health():
    return {
        "message": "Welcome to Multi-Tenant Document Management API",
        "status": "ok",
        "timestamp": datetime.utcnow()
    }