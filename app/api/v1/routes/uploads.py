from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from app.services.storage_service import StorageService
from app.core.auth import get_tenant_from_api_key
import os

router = APIRouter()

storage_service = StorageService()

@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_from_api_key)
):
    """Upload a file and store it locally under /uploads/{tenant_id}/."""
    file_path = await storage_service.save_file(tenant.id, file)
    return {"message": "File uploaded successfully", "path": file_path}


@router.get("/get", response_model=List[str])
async def list_uploaded_files(tenant=Depends(get_tenant_from_api_key)):
    """List all files uploaded by the tenant."""
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
