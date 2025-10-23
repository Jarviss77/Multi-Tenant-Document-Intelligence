import os
import shutil
from uuid import uuid4
from pathlib import Path
from fastapi import UploadFile

UPLOAD_DIR = Path("uploads")

class StorageService:
    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, tenant_id: str, file: UploadFile) -> str:
        """Save an uploaded file to the storage and return its path."""
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid4()}{file_extension}"
        if not (self.upload_dir / tenant_id).exists():
            (self.upload_dir / tenant_id).mkdir(parents=True, exist_ok=True)

        file_path = self.upload_dir / tenant_id /  unique_filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return str(file_path)

    def get_file_path(self, tenant_id: str, filename: str) -> Path:
        """Return path of a stored file."""
        return self.base_path / tenant_id / filename

    def delete_file(self, tenant_id: str, filename: str) -> bool:
        """Delete a stored file."""
        file_path = self.get_file_path(tenant_id, filename)
        if file_path.exists():
            file_path.unlink()
            return True
        return False