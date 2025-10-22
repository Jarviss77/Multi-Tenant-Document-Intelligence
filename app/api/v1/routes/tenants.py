from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.sessions import get_db
from app.db.models.tenant import Tenant
from app.core.security import generate_api_key, generate_hashed_api_key
import uuid

router = APIRouter()


class TenantCreate(BaseModel):
    name: str
    email: EmailStr


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    api_key: str

    class Config:
        from_attributes = True


@router.post("/onboard", response_model=TenantResponse, summary="Register tenant and generate API key")
async def onboard_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    existing_tenant = await db.execute(
        Tenant.__table__.select().where(
            (Tenant.name == payload.name) | (Tenant.email == payload.email)
        )
    )
    if existing_tenant.first():
        raise HTTPException(status_code=400, detail="Tenant with this name or email already exists")

    plain_api_key = generate_api_key()

    hashed_api_key = generate_hashed_api_key(plain_api_key)

    new_tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        api_key=hashed_api_key
    )

    db.add(new_tenant)
    await db.commit()
    await db.refresh(new_tenant)

    return TenantResponse(
        id=new_tenant.id,
        name=new_tenant.name,
        email=new_tenant.email,
        api_key=plain_api_key
    )

@router.get

@router.get("/tenant/{tenant_id}", response_model=TenantResponse, summary="Get tenant details by ID")
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        Tenant.__table__.select().where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        email=tenant.email,
        api_key="****"
    )