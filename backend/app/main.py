import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.sqlite import init_db
from app.database.qdrant_client import init_qdrant
from app.api import documents, facts, health, relationships, query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising databases")
    await init_db()
    await init_qdrant()
    logger.info("All systems ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Fact Knowledge Layer",
    description="Extract, link, and compare facts across any PDF documents.",
    version="1.0.0-phase3",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,         prefix="/api", tags=["health"])
app.include_router(documents.router,      prefix="/api", tags=["documents"])
app.include_router(facts.router,          prefix="/api", tags=["facts"])
app.include_router(relationships.router,  prefix="/api", tags=["relationships"])
app.include_router(query.router,          prefix="/api", tags=["query"])
app.version = "1.0.0-phase5"
