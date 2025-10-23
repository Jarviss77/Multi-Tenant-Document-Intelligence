import aiofiles
from typing import Optional

async def extract_text(file_path: str) -> str:
    """Reads file contents asynchronously."""
    async with aiofiles.open(file_path, "r") as f:
        return await f.read()