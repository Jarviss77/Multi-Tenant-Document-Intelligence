# app/core/auth.py
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.sessions import get_db
from app.db.models.tenant import Tenant
from app.core.security import verify_api_key
from sqlalchemy.ext.asyncio import AsyncSession

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

    # Find tenant by API key hash
    result = await db.execute(
        Tenant.__table__.select().where(
            Tenant.api_key == verify_api_key(api_key)  # This needs adjustment
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return tenant