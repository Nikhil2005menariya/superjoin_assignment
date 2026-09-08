import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    Modifier,
    PayloadSchemaType,
)
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

COLLECTION_NAME  = "facts"
CHUNK_COLLECTION = "doc_chunks"

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("Qdrant client not initialized")
    return _client


# bge-small-en-v1.5 → 384-dim
_DENSE_PARAMS  = VectorParams(size=384, distance=Distance.COSINE)
_SPARSE_PARAMS = SparseVectorParams(modifier=Modifier.IDF)


async def _ensure_collection(client: AsyncQdrantClient, name: str):
    """Create a dense + BM25 hybrid collection if it doesn't exist."""
    if await client.collection_exists(name):
        logger.info("Qdrant collection '%s' already exists", name)
        return
    await client.create_collection(
        collection_name=name,
        vectors_config={"dense": _DENSE_PARAMS},
        sparse_vectors_config={"bm25": _SPARSE_PARAMS},
    )
    await client.create_payload_index(name, "doc_id",   PayloadSchemaType.KEYWORD)
    await client.create_payload_index(name, "level",    PayloadSchemaType.KEYWORD)
    await client.create_payload_index(name, "page_num", PayloadSchemaType.INTEGER)
    logger.info("Created Qdrant collection '%s' (dense 384-dim + BM25)", name)


async def init_qdrant():
    global _client
    _client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=30,
    )

    if not await _client.collection_exists(COLLECTION_NAME):
        await _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={"dense": _DENSE_PARAMS},
            sparse_vectors_config={"bm25": _SPARSE_PARAMS},
        )
        for field, schema in [
            ("doc_id",            PayloadSchemaType.KEYWORD),
            ("subject",           PayloadSchemaType.KEYWORD),
            ("fact_type",         PayloadSchemaType.KEYWORD),
            ("evidence_verified", PayloadSchemaType.BOOL),
        ]:
            await _client.create_payload_index(COLLECTION_NAME, field, schema)
        logger.info("Created Qdrant collection '%s' (dense 384-dim + BM25)", COLLECTION_NAME)
    else:
        logger.info("Qdrant collection '%s' already exists", COLLECTION_NAME)

    await _ensure_collection(_client, CHUNK_COLLECTION)
