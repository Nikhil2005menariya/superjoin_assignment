"""
Integration tests for the FastAPI endpoints.
Uses httpx against the real app with a temp SQLite DB.
Qdrant calls are mocked so tests run without a running Qdrant instance.
"""

import io
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Health ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_ok(client):
    with patch("app.api.health.get_qdrant") as mock_qdrant:
        mock_qdrant.return_value.get_collections = AsyncMock(return_value=MagicMock())
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ─── Document upload ──────────────────────────────────────────────────────────

def _make_minimal_pdf() -> bytes:
    """Return a minimal but valid PDF byte string."""
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]
/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 120>>
stream
BT /F1 12 Tf 72 720 Td
(Revenue for FY2024 was Rs 21302 Crore.) Tj T*
(GDP growth rate was 6.4 per cent in 2024-25.) Tj
ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000438 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
510 %%EOF"""


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client):
    resp = await client.post(
        "/api/documents",
        files={"file": ("report.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_pdf_accepted(client):
    """Upload succeeds and returns doc_id + job_id."""
    pdf_bytes = _make_minimal_pdf()

    # Patch the background pipeline so it doesn't actually run
    with patch("app.api.documents.run_document_pipeline", new_callable=AsyncMock):
        resp = await client.post(
            "/api/documents",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "doc_id" in data
    assert "job_id" in data
    assert data["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_list_documents_returns_list(client):
    resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_nonexistent_document_404(client):
    resp = await client.get("/api/documents/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_then_get_document(client):
    pdf_bytes = _make_minimal_pdf()
    with patch("app.api.documents.run_document_pipeline", new_callable=AsyncMock):
        up = await client.post(
            "/api/documents",
            files={"file": ("doc2.pdf", pdf_bytes, "application/pdf")},
        )
    doc_id = up.json()["doc_id"]

    resp = await client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id
    assert resp.json()["filename"] == "doc2.pdf"


# ─── Chunks ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_chunks_empty_for_new_doc(client):
    pdf_bytes = _make_minimal_pdf()
    with patch("app.api.documents.run_document_pipeline", new_callable=AsyncMock):
        up = await client.post(
            "/api/documents",
            files={"file": ("doc3.pdf", pdf_bytes, "application/pdf")},
        )
    doc_id = up.json()["doc_id"]

    resp = await client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─── Facts ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_facts_returns_list(client):
    resp = await client.get("/api/facts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_nonexistent_fact_404(client):
    resp = await client.get("/api/facts/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_facts_summary_endpoint(client):
    resp = await client.get("/api/facts/stats/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "verified" in data
    assert "documents" in data


@pytest.mark.asyncio
async def test_facts_filter_by_doc(client):
    resp = await client.get("/api/facts", params={"doc_id": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_facts_filter_by_verified(client):
    resp = await client.get("/api/facts", params={"verified": "true"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
