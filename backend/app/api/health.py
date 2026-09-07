from fastapi import APIRouter
from app.database.qdrant_client import get_qdrant

router = APIRouter()


@router.get("/health")
async def health():
    try:
        qdrant = get_qdrant()
        collections = await qdrant.get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    return {
        "status": "ok",
        "qdrant": "ok" if qdrant_ok else "unavailable",
    }
