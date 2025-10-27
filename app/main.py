from fastapi import FastAPI
from app.api import router
from app.db.sessions import engine
from app.db.base import Base
from contextlib import asynccontextmanager
from app.db.base import load_all_models
from prometheus_fastapi_instrumentator import Instrumentator

load_all_models()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app = FastAPI(title="Multi-Tenant Document Management API", version="1.0.0")

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(router.api_router)