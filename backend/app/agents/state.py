from typing import TypedDict, List, Optional, Any
from app.models.schemas import PageData, ChunkData


class DocumentState(TypedDict):
    """State passed between LangGraph nodes for document processing."""
    doc_id: str
    job_id: str
    file_path: str

    # Populated by parse_pages node
    pages: List[PageData]
    total_pages: int

    # Populated by chunk_document node
    chunks: List[ChunkData]

    # Progress tracking
    stage: str
    progress: int
    message: str

    # Error propagation
    error: Optional[str]
