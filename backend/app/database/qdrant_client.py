import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    MultiVectorConfig,
    MultiVectorComparator,
    SparseVectorParams,
    Modifier,
    PayloadSchemaType,
)
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

COLLECTION_NAME = "facts"

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("Qdrant client not initialized")
    return _client


async def init_qdrant():
    global _client
    _client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=30,
    )

    exists = await _client.collection_exists(COLLECTION_NAME)
    if not exists:
        await _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                # Stage-1 dense ANN retrieval (bge-large-en-v1.5)
                "dense": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                    on_disk=False,
                ),
                # Stage-1 context retrieval (surrounding paragraph)
                "context": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                    on_disk=False,
                ),
                # Stage-2 ColBERT multi-vector MaxSim reranking
                "colbert": VectorParams(
                    size=128,
                    distance=Distance.COSINE,
                    multivector_config=MultiVectorConfig(
                        comparator=MultiVectorComparator.MAX_SIM,
                    ),
                ),
            },
            sparse_vectors_config={
                # Stage-1 BM25 keyword recall
                "bm25": SparseVectorParams(
                    modifier=Modifier.IDF,
                ),
            },
        )
        # Create payload indexes for efficient filtered search
        await _client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="doc_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await _client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="subject",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await _client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="fact_type",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await _client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="evidence_verified",
            field_schema=PayloadSchemaType.BOOL,
        )
        logger.info("Created Qdrant collection '%s' with dense+colbert+bm25 vectors", COLLECTION_NAME)
    else:
        logger.info("Qdrant collection '%s' already exists", COLLECTION_NAME)
