from typing import Optional
from fastapi import HTTPException, Depends, Header
from app.core.security import verify_jwt_token
from app.db.sessions import get_db
from app.db.models.tenant import Tenant
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib

async def get_tenant_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Extract and validate tenant from X-API-Key header
    """
    api_key = x_api_key

    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    provided_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await db.execute(select(Tenant).where(Tenant.api_key == provided_key_hash))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return tenant

async def get_payload_from_jwt_token(
    token: str = Header(..., alias="Authorization")
) -> dict:
    """
    Extract payload from JWT token in Authorization header
    """
    if not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    jwt_token = token[len("Bearer "):]

    # Here you would normally decode the JWT token and verify it
    # For simplicity, we'll just return a dummy payload

    payload = verify_jwt_token(token=jwt_token)

    return payload
