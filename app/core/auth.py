from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.sessions import get_db
from app.db.models.tenant import Tenant
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib

security = HTTPBearer()

async def get_tenant_from_api_key(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Extract and validate tenant from API key
    """
    api_key = credentials.credentials

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    provided_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await db.execute(
        select(Tenant).where(Tenant.api_key == provided_key_hash)
     )

    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return tenant