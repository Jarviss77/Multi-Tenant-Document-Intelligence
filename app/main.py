from fastapi import FastAPI
from app.api import router
from app.db.sessions import engine
from app.db.base import Base

app = FastAPI(title="Multi-Tenant Document Management API", version="1.0.0")

# app.include_router(tenants.router)
# app.include_router(documents.router)
app.include_router(router.api_router)


@app.on_event("startup")
async def startup_event():
    """Initialize DB tables if not already created (dev mode)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)