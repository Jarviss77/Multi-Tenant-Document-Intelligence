from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.sessions import get_db
from app.db.models.tenant import Tenant
from app.core.security import generate_api_key, generate_hashed_api_key, create_jwt_token
from app.core.auth import get_payload_from_jwt_token
from app.utils.logger import get_logger
import uuid

logger = get_logger(__name__)

router = APIRouter()


class TenantCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    api_key: str
    jwt_token: str

    model_config = ConfigDict(from_attributes=True)


@router.post("/onboard", response_model=TenantResponse, summary="Register tenant and generate API key")
async def onboard_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    existing_tenant = await db.execute(
        select(Tenant).where(
            (Tenant.name == payload.name) | (Tenant.email == payload.email)
        )
    )
    if existing_tenant.first():
        raise HTTPException(status_code=400, detail="Tenant with this name or email already exists")

    plain_api_key = generate_api_key()

    hashed_api_key = generate_hashed_api_key(plain_api_key)

    # generate jwt token

    new_tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        password=payload.password,
        api_key=hashed_api_key
    )

    jwt_token = create_jwt_token(new_tenant.id, payload.name, payload.password)

    db.add(new_tenant)
    await db.commit()
    await db.refresh(new_tenant)

    return TenantResponse(
        id=new_tenant.id,
        name=new_tenant.name,
        email=new_tenant.email,
        api_key=plain_api_key,
        jwt_token=jwt_token
    )

@router.patch("/get/api_key", summary="Get tenant API key by ID")
async def get_tenant_api_key(db: AsyncSession = Depends(get_db), tenant=Depends(get_payload_from_jwt_token)):
    logger.info(f"Generating API key for tenant ID: {tenant}")
    result = await db.execute(
        select(Tenant).where(
            Tenant.id == tenant['tenant_id']
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    plain_api_key = generate_api_key()

    hashed_api_key = generate_hashed_api_key(plain_api_key)

    tenant.api_key = hashed_api_key
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return {
        "api_key": plain_api_key
    }

@router.post("/tenant/login", summary="give tenant jwt token by credentials")
async def tenant_login(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tenant).where(
            (Tenant.name == payload.name) & (Tenant.password == payload.password) & (Tenant.email == payload.email)
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    jwt_token = create_jwt_token(tenant.id, payload.name, payload.password)

    return {
        "jwt_token": jwt_token
    }


# testing route to get tenant details by id
@router.get("/tenant/{tenant_id}", response_model=TenantResponse, summary="Get tenant details by ID")
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
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