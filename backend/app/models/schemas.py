from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    extracting = "extracting"
    embedding = "embedding"
    comparing = "comparing"
    done = "done"
    failed = "failed"


class JobStage(str, Enum):
    pending = "pending"
    parsing = "parsing"
    chunking = "chunking"
    extracting = "extracting"
    embedding = "embedding"
    comparing = "comparing"
    done = "done"
    failed = "failed"


class RelationshipType(str, Enum):
    corroborates = "CORROBORATES"
    contradicts = "CONTRADICTS"
    reconciles = "RECONCILES"
    supersedes = "SUPERSEDES"
    refines = "REFINES"


class FactType(str, Enum):
    numerical = "numerical"
    semantic = "semantic"
    relational = "relational"


# --- Document models ---

class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: Optional[int]
    page_count: Optional[int]
    status: DocumentStatus
    error_msg: Optional[str]
    created_at: str
    updated_at: str


class JobResponse(BaseModel):
    id: str
    doc_id: str
    status: str
    stage: str
    progress: int
    total_pages: int
    current_page: int
    message: Optional[str]
    error_msg: Optional[str]
    updated_at: str


# --- Chunk models ---

class ChunkResponse(BaseModel):
    id: str
    doc_id: str
    parent_id: Optional[str]
    level: str
    page_num: Optional[int]
    section_path: Optional[str]
    raw_text: str
    source_type: str
    chunk_index: int


# --- Fact models (used from Phase 2 onward, defined here for schema completeness) ---

class FactResponse(BaseModel):
    id: str
    doc_id: str
    chunk_id: Optional[str]
    statement: str
    subject: Optional[str]
    predicate: Optional[str]
    metric: Optional[str]
    value_raw: Optional[str]
    value_normalized: Optional[float]
    unit_raw: Optional[str]
    unit_canonical: Optional[str]
    time_period_raw: Optional[str]
    time_start: Optional[str]
    time_end: Optional[str]
    scope: Optional[str]
    qualifier: Optional[str]
    fact_type: str
    confidence: float
    evidence_verified: bool
    exact_quote: Optional[str]
    attributes: dict = {}
    created_at: str


class RelationshipResponse(BaseModel):
    id: str
    fact_a_id: str
    fact_b_id: str
    type: str
    explanation: Optional[str]
    reconciliation_context: Optional[str]
    confidence: float
    created_at: str


# --- Internal processing types ---

class PageData(BaseModel):
    page_num: int
    text: str
    tables: List[List[List[Optional[str]]]] = []
    words: List[dict] = []
    source_type: str = "text"
    char_count: int = 0


class ChunkData(BaseModel):
    id: str
    doc_id: str
    parent_id: Optional[str] = None
    level: str
    page_num: int
    section_path: str = ""
    raw_text: str
    bbox: List[dict] = []
    source_type: str = "text"
    chunk_index: int = 0
